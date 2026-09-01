"""SKU + variation mapping engine.

Binding safety rule: map_sku_async() can only ever return
MappingStatus.MATCHED via an exact row previously written by
create_explicit_mapping_async(). A fuzzy match is always returned as
NEEDS_REVIEW / CONFLICT / NOT_FOUND — never MATCHED, regardless of
confidence score. This means a fuzzy suggestion can never, by itself,
cause inventory to be reserved or an order to be fulfilled — see
services/fulfillment/workflow.py's _step_check_inventory.

Follows the same synchronous-facade-over-async-implementation pattern as
services/order_service.py (see that module's docstring for the full
rationale): the real logic is async (map_sku_async/
create_explicit_mapping_async, taking an AsyncSession), and
SkuMappingEngine is a synchronous facade for the legacy synchronous
FulfillmentWorkflowEngine to call, bridged via the same dedicated bridge
loop order_service.py already runs.
"""

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import SkuMapping
from app.schemas.sku_mapping import MappingResult, MappingStatus
from app.services.sku_mapping import matcher

logger = logging.getLogger(__name__)

# Two candidates within this delta of each other are treated as ambiguous
# rather than auto-picking the top one.
AMBIGUITY_DELTA = 0.03


async def map_sku_async(
    tiktok_sku: str,
    variation: str | None,
    organization_id: UUID,
    db: AsyncSession,
) -> MappingResult:
    """Resolve a TikTok SKU + variation to an Amazon SKU/ASIN.

    Never writes — side-effect-free on retry. See module docstring for
    the binding "fuzzy is never MATCHED" rule.
    """
    stmt = select(SkuMapping).where(
        SkuMapping.organization_id == organization_id,
        SkuMapping.tiktok_sku == tiktok_sku,
        SkuMapping.variation == variation,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is not None:
        # Deterministic exact match — the unique constraint on
        # (organization_id, tiktok_sku, variation) guarantees at most one
        # row, so this is unambiguous by construction. Returned exactly
        # as stored: this is the ONLY path that can yield MATCHED.
        return MappingResult(
            tiktok_sku=row.tiktok_sku,
            variation=row.variation,
            amazon_sku=row.amazon_sku,
            asin=row.asin,
            confidence_score=row.confidence_score,
            status=MappingStatus(row.status),
            reason=None if row.status == "matched" else f"Stored mapping status: {row.status}",
        )

    candidates = await matcher.find_candidates(tiktok_sku, variation, organization_id, db)

    if not candidates:
        return MappingResult(
            tiktok_sku=tiktok_sku,
            variation=variation,
            amazon_sku=None,
            asin=None,
            confidence_score=0.0,
            status=MappingStatus.NOT_FOUND,
            reason="No known mapping or similar confirmed mapping found",
        )

    top = candidates[0]
    if top.score < settings.SKU_MAPPING_CONFIDENCE_THRESHOLD:
        return MappingResult(
            tiktok_sku=tiktok_sku,
            variation=variation,
            amazon_sku=None,
            asin=None,
            confidence_score=top.score,
            status=MappingStatus.NOT_FOUND,
            reason=(
                f"Best candidate confidence {top.score:.2f} below suggestion floor "
                f"{settings.SKU_MAPPING_CONFIDENCE_THRESHOLD:.2f} — not worth suggesting"
            ),
        )

    if len(candidates) > 1 and (top.score - candidates[1].score) < AMBIGUITY_DELTA:
        return MappingResult(
            tiktok_sku=tiktok_sku,
            variation=variation,
            amazon_sku=None,
            asin=None,
            confidence_score=top.score,
            status=MappingStatus.CONFLICT,
            reason="Multiple equally plausible mappings found — needs manual resolution",
        )

    # A fuzzy suggestion — surfaced for a human, NEVER auto-applied.
    return MappingResult(
        tiktok_sku=tiktok_sku,
        variation=variation,
        amazon_sku=top.amazon_sku,
        asin=top.asin,
        confidence_score=top.score,
        status=MappingStatus.NEEDS_REVIEW,
        reason="Fuzzy suggestion — not auto-applied; confirm via create_explicit_mapping",
    )


async def create_explicit_mapping_async(
    tiktok_sku: str,
    variation: str | None,
    amazon_sku: str,
    asin: str | None,
    organization_id: UUID,
    db: AsyncSession,
) -> SkuMapping:
    """Write a human-confirmed mapping.

    The ONLY function that can produce a status="matched" row — a fuzzy
    match never writes through this path automatically.
    """
    stmt = select(SkuMapping).where(
        SkuMapping.organization_id == organization_id,
        SkuMapping.tiktok_sku == tiktok_sku,
        SkuMapping.variation == variation,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        row = SkuMapping(
            id=uuid4(),
            organization_id=organization_id,
            tiktok_sku=tiktok_sku,
            variation=variation,
        )
        db.add(row)

    row.amazon_sku = amazon_sku
    row.asin = asin
    row.confidence_score = 1.0
    row.status = "matched"
    row.source = "explicit"

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(row)
    logger.info("Explicit SKU mapping confirmed: %s/%s -> %s", tiktok_sku, variation, amazon_sku)
    return row


# ---------------------------------------------------------------------------
# Synchronous bridge — see module docstring.
# Used ONLY by services/fulfillment/workflow.py, mirroring
# services/order_service.py's OrderService legacy facade exactly.
# ---------------------------------------------------------------------------


class SkuMappingEngine:
    """Synchronous facade over the async implementation above, for the
    legacy synchronous FulfillmentWorkflowEngine."""

    def map_sku(
        self, tiktok_sku: str, variation: str | None, organization_id: UUID
    ) -> MappingResult:
        from app.services.order_service import bridge_session, run_on_bridge_loop

        async def _run() -> MappingResult:
            async with bridge_session() as db:
                return await map_sku_async(tiktok_sku, variation, organization_id, db)

        return run_on_bridge_loop(_run())

    def create_explicit_mapping(
        self,
        tiktok_sku: str,
        variation: str | None,
        amazon_sku: str,
        asin: str | None,
        organization_id: UUID,
    ) -> SkuMapping:
        from app.services.order_service import bridge_session, run_on_bridge_loop

        async def _run() -> SkuMapping:
            async with bridge_session() as db:
                return await create_explicit_mapping_async(
                    tiktok_sku, variation, amazon_sku, asin, organization_id, db
                )

        return run_on_bridge_loop(_run())


sku_mapping_engine = SkuMappingEngine()
