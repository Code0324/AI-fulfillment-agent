"""TikTok Shop Open API authentication and request signing.

Handles OAuth2-style token refresh and per-request HMAC-SHA256 signing for
TikTok Shop API access. All credentials are kept in memory only — never
logged or exposed.

VERIFICATION STATUS (see docs/tiktok-integration.md for the full record):
- OAuth token-exchange/refresh shape (grant_type=authorized_code /
  refresh_token, app_key/app_secret/refresh_token params, response
  carrying access_token/refresh_token/shop_cipher) is corroborated against
  TikTok's own developer documentation.
- The request-signing SHAPE (HMAC-SHA256 over path + sorted query params +
  body, keyed by app_secret, passed as a `sign` query parameter) is
  corroborated against TikTok's own webhook-verification reference doc,
  which explicitly contrasts it with webhook signing.
- The BYTE-EXACT signing algorithm (whether access_token/app_key/timestamp
  are included in the signed string, and their exact ordering) and the
  exact token endpoint path could NOT be verified via live documentation
  fetch in this session (TikTok's Partner Center docs are a JS-rendered
  SPA that returns only a page shell to automated fetches). TOKEN_URL
  below reflects TikTok Shop Partner API v2's documented token-endpoint
  pattern from general knowledge, NOT a value confirmed via live fetch
  this session — it MUST be re-verified against partner.tiktokshop.com
  (or the interactive docs available once a developer app is approved)
  before this is ever used against TikTok's real API.

CRITICAL SAFETY RULES:
- Never log app_secret, access_token, or refresh_token
- Never expose credentials to frontend
- Access tokens are memory-only
- Never fabricate a token or a successful auth result
"""

import hashlib
import hmac
import logging
import os
import time
from urllib.parse import urlencode

import httpx

from app.core.security import redact_secret

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------

# NOT verified via live fetch this session — see module docstring.
# RE-VERIFY before first production use.
TIKTOK_TOKEN_REFRESH_URL = "https://auth.tiktok-shops.com/api/v2/token/refresh"

TOKEN_EXPIRY_BUFFER_SECONDS = 300  # refresh 5 minutes before expiry
DEFAULT_TOKEN_EXPIRY_SECONDS = 3600


class TikTokAuthenticationError(Exception):
    """TikTok Shop authentication failed."""

    def __init__(self, message: str = "TikTok Shop authentication failed", recoverable: bool = True):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


def sign_request(path: str, params: dict[str, str], body: str, app_secret: str) -> str:
    """Compute a TikTok Shop API request signature.

    Implements the CORROBORATED general shape only (HMAC-SHA256 over
    path + sorted query params + body, keyed by app_secret) — see the
    module docstring's VERIFICATION STATUS. The exact inclusion/exclusion
    of params like `access_token`/`app_key`/`timestamp` in the signed
    string is UNVERIFIED and must be confirmed against TikTok's live
    signature-generation reference before this is trusted for a real call.

    Args:
        path: API path, e.g. "/order/202309/orders/search"
        params: query parameters to include in the signed string, EXCLUDING `sign` itself
        body: raw request body (empty string for GET requests)
        app_secret: the app's secret, used as the HMAC key

    Returns:
        Lowercase hex-encoded HMAC-SHA256 signature.
    """
    sorted_params = "".join(f"{key}{params[key]}" for key in sorted(params))
    message = f"{path}{sorted_params}{body}"
    return hmac.new(
        app_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class TikTokTokenManager:
    """Manages TikTok Shop access tokens with refresh.

    This class handles:
    - Refresh of the access token using a long-lived refresh token
    - Token caching in memory only
    - Revoked/expired refresh token handling

    SECURITY:
    - Never logs credentials
    - Never exposes tokens to external systems
    - Tokens are memory-only
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        refresh_token: str,
        access_token: str | None = None,
    ):
        """Initialize the TikTok Shop token manager.

        Args:
            app_key: TikTok Shop app key
            app_secret: TikTok Shop app secret
            refresh_token: TikTok Shop refresh token from authorization
            access_token: an already-issued access token, if available
                (avoids an unnecessary refresh call on first use)

        SECURITY: These values are stored in memory only and never logged.
        """
        if not app_key or not app_secret or not refresh_token:
            raise TikTokAuthenticationError(
                "Missing required TikTok Shop credentials: app_key, app_secret, "
                "and refresh_token are all required"
            )

        self._app_key = app_key
        self._app_secret = app_secret
        self._refresh_token = refresh_token

        self._access_token: str | None = access_token
        # If we were handed an access token with no known expiry, treat it
        # as already needing a refresh on first real use rather than
        # assuming it's fresh — never trust an unverified expiry.
        self._token_expires_at: float = 0
        self._token_refresh_count: int = 0

        logger.info("TikTok Shop token manager initialized (app_key=%s)", redact_secret(app_key))

    @property
    def app_secret(self) -> str:
        """The app secret, for request signing. Never log this."""
        return self._app_secret

    @property
    def app_key(self) -> str:
        return self._app_key

    @property
    def is_configured(self) -> bool:
        """Check if credentials are configured."""
        return bool(self._app_key and self._app_secret and self._refresh_token)

    @property
    def token_expires_in(self) -> int:
        """Seconds until token expires (or 0 if expired/not set)."""
        if self._token_expires_at == 0:
            return 0
        return max(0, int(self._token_expires_at - time.time()))

    @property
    def refresh_count(self) -> int:
        """Number of times the token has been refreshed."""
        return self._token_refresh_count

    def _is_token_valid(self) -> bool:
        if self._access_token is None:
            return False
        return time.time() < (self._token_expires_at - TOKEN_EXPIRY_BUFFER_SECONDS)

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self._is_token_valid():
            return self._access_token  # type: ignore
        return await self._refresh_token_request()

    def get_access_token_sync(self) -> str:
        """Synchronous version: get a valid access token."""
        if self._is_token_valid():
            return self._access_token  # type: ignore
        return self._refresh_token_request_sync()

    async def _refresh_token_request(self) -> str:
        params = {
            "app_key": self._app_key,
            "app_secret": self._app_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        url = f"{TIKTOK_TOKEN_REFRESH_URL}?{urlencode(params)}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                return self._handle_token_response(response)
        except httpx.TimeoutException:
            raise TikTokAuthenticationError("TikTok Shop token request timed out", recoverable=True)
        except httpx.NetworkError as e:
            raise TikTokAuthenticationError(f"TikTok Shop network error: {type(e).__name__}", recoverable=True)
        except Exception as e:
            if isinstance(e, TikTokAuthenticationError):
                raise
            raise TikTokAuthenticationError(
                f"Unexpected error during TikTok Shop token refresh: {type(e).__name__}", recoverable=True
            )

    def _refresh_token_request_sync(self) -> str:
        params = {
            "app_key": self._app_key,
            "app_secret": self._app_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        url = f"{TIKTOK_TOKEN_REFRESH_URL}?{urlencode(params)}"

        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=30.0)
                return self._handle_token_response(response)
        except httpx.TimeoutException:
            raise TikTokAuthenticationError("TikTok Shop token request timed out", recoverable=True)
        except httpx.NetworkError as e:
            raise TikTokAuthenticationError(f"TikTok Shop network error: {type(e).__name__}", recoverable=True)
        except Exception as e:
            if isinstance(e, TikTokAuthenticationError):
                raise
            raise TikTokAuthenticationError(
                f"Unexpected error during TikTok Shop token refresh: {type(e).__name__}", recoverable=True
            )

    def _handle_token_response(self, response: httpx.Response) -> str:
        """Process a token response and update the cache.

        The exact response field names (access_token/access_token_expire_in
        vs. expires_in, etc.) are corroborated at a high level only — this
        accepts a couple of plausible key spellings but never fabricates a
        token if none is present.
        """
        if response.status_code == 200:
            try:
                body = response.json()
            except Exception:
                raise TikTokAuthenticationError(
                    "TikTok Shop token response was not valid JSON", recoverable=False
                )

            # TikTok Shop wraps payloads under "data" in most Open API
            # responses — accept both shapes rather than assuming one.
            payload = body.get("data", body) if isinstance(body, dict) else {}
            access_token = payload.get("access_token")
            expires_in = payload.get("access_token_expire_in") or payload.get(
                "expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS
            )

            if not access_token:
                raise TikTokAuthenticationError(
                    "TikTok Shop token response missing access_token — refusing to "
                    "fabricate a token",
                    recoverable=False,
                )

            self._access_token = access_token
            self._token_expires_at = time.time() + expires_in
            self._token_refresh_count += 1

            logger.info(
                "TikTok Shop token refreshed successfully (expires_in=%s, refresh_count=%d)",
                expires_in,
                self._token_refresh_count,
            )
            return self._access_token

        try:
            body = response.json()
            error_code = body.get("code", "unknown")
            error_message = body.get("message", "No message")
        except Exception:
            error_code = "parse_error"
            error_message = response.text[:200]

        if response.status_code in (401, 403):
            raise TikTokAuthenticationError(
                f"TikTok Shop authentication failed: {error_code} — {error_message}",
                recoverable=False,
            )
        if response.status_code == 429:
            raise TikTokAuthenticationError("TikTok Shop rate limited — try again later", recoverable=True)
        if response.status_code >= 500:
            raise TikTokAuthenticationError(
                f"TikTok Shop server error ({response.status_code})", recoverable=True
            )
        raise TikTokAuthenticationError(
            f"TikTok Shop authentication failed: {error_code} — {error_message}", recoverable=False
        )

    def invalidate_token(self) -> None:
        """Invalidate the current token (force refresh on next request)."""
        self._access_token = None
        self._token_expires_at = 0
        logger.info("TikTok Shop access token invalidated")

    def clear(self) -> None:
        """Clear all token state (used by tests)."""
        self._access_token = None
        self._token_expires_at = 0
        self._token_refresh_count = 0
        logger.info("TikTok Shop token manager cleared")


def create_tiktok_token_manager_from_env() -> TikTokTokenManager | None:
    """Create a TikTok Shop token manager from environment variables.

    Returns:
        TikTokTokenManager if all credentials are set, None otherwise —
        never raises for missing config, so app startup never crashes on
        an unconfigured TikTok integration.

    Environment Variables:
        TIKTOK_APP_KEY, TIKTOK_APP_SECRET, TIKTOK_REFRESH_TOKEN,
        TIKTOK_ACCESS_TOKEN (optional — avoids an initial refresh call)
    """
    app_key = os.getenv("TIKTOK_APP_KEY", "")
    app_secret = os.getenv("TIKTOK_APP_SECRET", "")
    refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN", "")
    access_token = os.getenv("TIKTOK_ACCESS_TOKEN", "") or None

    if not all([app_key, app_secret, refresh_token]):
        logger.info("TikTok Shop credentials not configured — TikTok integration disabled")
        return None

    try:
        manager = TikTokTokenManager(
            app_key=app_key,
            app_secret=app_secret,
            refresh_token=refresh_token,
            access_token=access_token,
        )
        logger.info("TikTok Shop token manager created from environment")
        return manager
    except TikTokAuthenticationError as e:
        logger.warning("Failed to create TikTok Shop token manager: %s", e.message)
        return None
