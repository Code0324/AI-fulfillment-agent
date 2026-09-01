"""Fuzzy matching for unresolved TikTok SKU + variation lookups.

Compares a new (tiktok_sku, variation) pair against the corpus of
already-explicitly-confirmed SkuMapping rows for the same organization —
never against other fuzzy suggestions, which could compound uncertainty,
and never against app/services/inventory_service.py's InventoryItem
table, which has no ASIN column and so cannot supply one.

Uses stdlib difflib.SequenceMatcher. No fuzzy-match dependency is
currently in backend/requirements.txt; adding one (e.g. rapidfuzz) is a
cheap later upgrade if match quality needs it — this keeps the SKU
mapping engine dependency-free for now.

This module never decides a mapping is trustworthy on its own — see
engine.py for how candidates are turned into a MappingResult, and the
binding rule that a fuzzy match is never auto-promoted to "matched".
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SkuMapping


@dataclass
class MatchCandidate:
    """A candidate Amazon SKU/ASIN for an unresolved TikTok SKU + variation."""

    tiktok_sku: str
    variation: str | None
    amazon_sku: str | None
    asin: str | None
    score: float


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _key(sku: str, variation: str | None) -> str:
    return f"{sku}::{variation or ''}"


async def find_candidates(
    tiktok_sku: str,
    variation: str | None,
    organization_id: UUID,
    db: AsyncSession,
) -> list[MatchCandidate]:
    """Return candidates sorted by score, descending (best first).

    Only compares against rows with status="matched", source="explicit"
    — i.e. mappings a human has actually confirmed via
    engine.create_explicit_mapping_async, so a fuzzy suggestion is always
    grounded in a real prior confirmation, not another guess.
    """
    stmt = select(SkuMapping).where(
        SkuMapping.organization_id == organization_id,
        SkuMapping.status == "matched",
        SkuMapping.source == "explicit",
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    target = _key(tiktok_sku, variation)
    candidates = [
        MatchCandidate(
            tiktok_sku=row.tiktok_sku,
            variation=row.variation,
            amazon_sku=row.amazon_sku,
            asin=row.asin,
            score=_similarity(target, _key(row.tiktok_sku, row.variation)),
        )
        for row in rows
    ]
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates
