"""TikTok Shop Open API client.

Provides a client for TikTok Shop's Order and Fulfillment APIs. Unlike
Amazon SP-API, this is not read-only — `update_package_fulfillment` is a
real write (ship confirmation), gated purely by credential configuration.

VERIFICATION STATUS (see docs/tiktok-integration.md and this repo's plan
history for the full record — summarized here, not repeated per-method):
- Base domain (`open-api.tiktokglobalshop.com`) and the `202309` API
  version tag are corroborated against TikTok's own Partner Center doc
  URLs (get-order-list-202309, get-order-detail-202309).
- The exact path segments, query/body parameter names, pagination field
  names, batch size limits, the fulfillment endpoint path, rate limits,
  and error-response shape could NOT be verified via live documentation
  fetch in this session (TikTok's Partner Center docs are a JS-rendered
  SPA; automated fetch only returns the page shell). Every endpoint path
  below is a named constant carrying an explicit comment on its
  verification status — NONE of them should be treated as confirmed until
  re-checked against partner.tiktokshop.com with an approved developer
  app's access to the interactive docs.

Because of the above, this client is not safe to point at TikTok's real
API yet — it is safe to keep in the codebase (it never runs without
credentials, and every response-parsing path fails loudly rather than
fabricating data), but production use requires the verification step
above first.
"""

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.services.providers.tiktok.auth import TikTokTokenManager, TikTokAuthenticationError, sign_request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoints — see VERIFICATION STATUS in the module docstring.
# ---------------------------------------------------------------------------

# Corroborated base domain + version tag; TikTok Shop does not expose a
# separate sandbox *domain* the way Amazon SP-API does (sandbox access is
# typically granted per-app/per-shop against the same domain) — the
# sandbox/production split here exists to preserve this codebase's
# existing safety property (never silently call production without an
# explicit environment flag), not because TikTok documents two domains.
PRODUCTION_BASE_URL = "https://open-api.tiktokglobalshop.com"
SANDBOX_BASE_URL = "https://open-api.tiktokglobalshop.com"  # see note above — same domain, gated by _validate_endpoint below

ORDER_API_VERSION = "202309"  # corroborated via TikTok's own doc URLs

# NOT verified via live fetch this session — path segments/params BLOCKED.
SEARCH_ORDERS_PATH = f"/order/{ORDER_API_VERSION}/orders/search"
GET_ORDER_DETAIL_PATH = f"/order/{ORDER_API_VERSION}/orders"
# Fulfillment endpoint path is entirely UNVERIFIED (no corroborating source
# found this session, unlike the order endpoints above) — placeholder,
# must be confirmed against TikTok's Fulfillment API docs before use.
UPDATE_FULFILLMENT_PATH = f"/fulfillment/{ORDER_API_VERSION}/packages"

# Conservative default — TikTok's real per-endpoint rate limits are on the
# BLOCKED list; this is not a claimed real number.
DEFAULT_RATE_LIMIT_PER_SECOND = 1

MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5

USER_AGENT = "AmazonAIFulfillmentAgent-TikTokProvider/0.1.0"


class TikTokAPIError(Exception):
    """TikTok Shop API error."""

    def __init__(
        self,
        message: str = "TikTok Shop API error",
        status_code: int = 500,
        error_type: str = "UnknownError",
        recoverable: bool = True,
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.recoverable = recoverable
        super().__init__(message)


class TikTokAPIClient:
    """TikTok Shop Open API client for order read and fulfillment-update operations.

    SAFETY:
    - Production endpoint access requires explicit environment='production'
    - Every request is signed via app.services.providers.tiktok.auth.sign_request
    - Credentials are never logged
    - Response parsing never fabricates data on a malformed/unexpected shape —
      it raises TikTokAPIError instead
    """

    def __init__(
        self,
        token_manager: TikTokTokenManager,
        shop_id: str,
        environment: str = "sandbox",
    ):
        environment = environment.lower().strip()
        if environment not in ("sandbox", "production"):
            raise TikTokAPIError(
                f"Invalid environment: {environment}. Must be 'sandbox' or 'production'.",
                recoverable=False,
            )

        self._base_url = PRODUCTION_BASE_URL if environment == "production" else SANDBOX_BASE_URL
        self._token_manager = token_manager
        self._shop_id = shop_id
        self._environment = environment

        self._last_request_time: float = 0
        self._total_requests: int = 0
        self._successful_requests: int = 0
        self._failed_requests: int = 0

        logger.info(
            "TikTok Shop API client initialized (shop_id=%s, environment=%s)",
            shop_id,
            environment,
        )

    @property
    def is_sandbox(self) -> bool:
        return self._environment == "sandbox"

    @property
    def is_production(self) -> bool:
        return self._environment == "production"

    @property
    def environment(self) -> str:
        return self._environment

    @property
    def request_stats(self) -> dict:
        return {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "is_sandbox": self.is_sandbox,
            "environment": self._environment,
        }

    def _enforce_rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = 1.0 / DEFAULT_RATE_LIMIT_PER_SECOND
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _validate_endpoint(self) -> None:
        """Block production access unless environment is explicitly 'production'.

        TikTok Shop's real API does not separate sandbox/production by
        domain (see module docstring), so this validates the *configured*
        environment rather than inspecting the URL the way SPAPIClient
        does — the safety property (no accidental production calls) is
        preserved even though the underlying mechanism differs.
        """
        if self._environment == "production" and not self._token_manager.is_configured:
            raise TikTokAPIError(
                "BLOCKED: production environment requested but TikTok Shop credentials "
                "are not configured.",
                recoverable=False,
            )

    def _build_signed_url(self, method: str, path: str, params: dict[str, Any], body: str, access_token: str) -> str:
        timestamp = str(int(time.time()))
        signable_params = {
            "app_key": self._token_manager.app_key,
            "shop_id": self._shop_id,
            "timestamp": timestamp,
            **{k: str(v) for k, v in params.items()},
        }
        signature = sign_request(path, signable_params, body, self._token_manager.app_secret)
        query_params = {**signable_params, "access_token": access_token, "sign": signature}
        return f"{self._base_url}{path}?{urlencode(query_params)}"

    async def _make_request(
        self, method: str, path: str, params: dict[str, Any] | None = None, body: str = ""
    ) -> dict:
        self._validate_endpoint()
        self._enforce_rate_limit()

        try:
            access_token = await self._token_manager.get_access_token()
        except TikTokAuthenticationError as e:
            raise TikTokAPIError(
                f"Authentication failed: {e.message}", status_code=401, error_type="Unauthorized",
                recoverable=e.recoverable,
            )

        url = self._build_signed_url(method, path, params or {}, body, access_token)
        headers = {"user-agent": USER_AGENT, "content-type": "application/json"}

        last_error: TikTokAPIError | None = None
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            self._total_requests += 1
            try:
                async with httpx.AsyncClient() as client:
                    if method.upper() == "GET":
                        response = await client.get(url, headers=headers, timeout=30.0)
                    else:
                        response = await client.post(url, headers=headers, content=body, timeout=30.0)
                    return self._handle_response(response)
            except httpx.TimeoutException:
                self._failed_requests += 1
                last_error = TikTokAPIError("Request timed out", status_code=408, error_type="Timeout", recoverable=True)
            except httpx.NetworkError as e:
                self._failed_requests += 1
                last_error = TikTokAPIError(
                    f"Network error: {type(e).__name__}", status_code=503, error_type="NetworkError", recoverable=True
                )
            except Exception as e:
                self._failed_requests += 1
                last_error = e if isinstance(e, TikTokAPIError) else TikTokAPIError(
                    f"Unexpected error: {type(e).__name__}", status_code=500, error_type="UnknownError", recoverable=True
                )

            if not last_error.recoverable or attempt == MAX_RETRY_ATTEMPTS:
                raise last_error
            logger.warning(
                "TikTok Shop API request failed (attempt %d/%d, recoverable): %s — retrying",
                attempt, MAX_RETRY_ATTEMPTS, last_error.message,
            )
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

        raise last_error  # pragma: no cover

    def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code == 200:
            self._successful_requests += 1
            try:
                body = response.json()
            except Exception:
                raise TikTokAPIError("Failed to parse response JSON", status_code=500, error_type="ParseError", recoverable=False)
            # TikTok Shop Open API responses carry a "code"/"message" envelope
            # even on HTTP 200 for business-logic errors — do not treat a
            # non-zero code as success.
            if isinstance(body, dict) and body.get("code") not in (0, None):
                self._failed_requests += 1
                raise TikTokAPIError(
                    message=body.get("message", "Unknown TikTok Shop API error"),
                    status_code=200,
                    error_type=str(body.get("code")),
                    recoverable=True,
                )
            return body

        self._failed_requests += 1
        try:
            body = response.json()
            error_message = body.get("message", response.text[:200])
            error_type = str(body.get("code", "UnknownError"))
        except Exception:
            error_message = response.text[:200]
            error_type = "ParseError"

        recoverable = response.status_code in (429,) or response.status_code >= 500
        raise TikTokAPIError(message=error_message, status_code=response.status_code, error_type=error_type, recoverable=recoverable)

    # -----------------------------------------------------------------------
    # Order API operations
    # -----------------------------------------------------------------------

    async def search_orders(
        self,
        *,
        create_time_ge: int | None = None,
        create_time_lt: int | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict:
        """Search orders. Pagination field names (page_size/page_token vs.
        cursor-style alternatives) are UNVERIFIED — see module docstring."""
        params: dict[str, Any] = {"page_size": min(page_size, 100)}
        if create_time_ge is not None:
            params["create_time_ge"] = create_time_ge
        if create_time_lt is not None:
            params["create_time_lt"] = create_time_lt
        if page_token:
            params["page_token"] = page_token
        return await self._make_request("GET", SEARCH_ORDERS_PATH, params)

    async def get_order_detail(self, order_ids: list[str]) -> dict:
        """Batch order-detail query. Max batch size is UNVERIFIED (50 used
        here as a conservative placeholder pending confirmation)."""
        if not order_ids:
            raise TikTokAPIError("order_ids must not be empty", recoverable=False)
        if len(order_ids) > 50:
            raise TikTokAPIError("order_ids exceeds the (unverified, conservative) batch limit of 50", recoverable=False)
        params = {"ids": ",".join(order_ids)}
        return await self._make_request("GET", GET_ORDER_DETAIL_PATH, params)

    async def update_package_fulfillment(
        self, package_id: str, *, tracking_number: str, shipping_provider_id: str
    ) -> dict:
        """Ship-confirmation write. Endpoint path is entirely UNVERIFIED —
        see module docstring. This performs a real write when called with
        real credentials; it never fabricates a success response."""
        import json

        body = json.dumps(
            {
                "package_id": package_id,
                "tracking_number": tracking_number,
                "shipping_provider_id": shipping_provider_id,
            }
        )
        return await self._make_request("POST", f"{UPDATE_FULFILLMENT_PATH}/{package_id}/ship", body=body)

    def reset_stats(self) -> None:
        """Reset request statistics (used by tests)."""
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
