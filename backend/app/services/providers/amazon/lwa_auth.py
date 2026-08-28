"""LWA (Login with Amazon) Authentication for Amazon SP-API.

Handles OAuth2 token exchange, refresh, and caching for SP-API access.
All credentials are kept in memory only — never logged or exposed.

CRITICAL SAFETY RULES:
- Never log client_secret, refresh_token, or access_token
- Never expose credentials to frontend
- Access tokens are memory-only
- Handle token expiration and refresh
- Handle revoked refresh tokens
- Production endpoints MUST NOT be reachable during CHUNK 1V
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.security import redact_secret

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------

# LWA Token endpoint (same for sandbox and production)
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

# Token expiration buffer (refresh 5 minutes before expiry)
TOKEN_EXPIRY_BUFFER_SECONDS = 300

# Default token expiration (1 hour)
DEFAULT_TOKEN_EXPIRY_SECONDS = 3600


class LWAAuthenticationError(Exception):
    """LWA authentication failed."""
    def __init__(self, message: str = "LWA authentication failed", recoverable: bool = True):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


class LWATokenManager:
    """Manages LWA access tokens with automatic refresh.
    
    This class handles:
    - Initial token acquisition using refresh_token
    - Automatic token refresh before expiration
    - Token caching in memory only
    - Revoked refresh token handling
    
    SECURITY:
    - Never logs credentials
    - Never exposes tokens to external systems
    - Tokens are memory-only
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ):
        """Initialize LWA token manager.
        
        Args:
            client_id: Amazon SP-API application client ID
            client_secret: Amazon SP-API application client secret
            refresh_token: LWA refresh token from authorization
            
        SECURITY: These values are stored in memory only and never logged.
        """
        if not client_id or not client_secret or not refresh_token:
            raise LWAAuthenticationError(
                "Missing required LWA credentials: client_id, client_secret, and refresh_token are all required"
            )
        
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        
        # Token cache (memory only)
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self._token_type: str = "bearer"
        
        # Statistics
        self._token_refresh_count: int = 0
        self._last_refresh_at: float | None = None
        
        logger.info("LWA token manager initialized (client_id=%s)", redact_secret(client_id))
    
    @property
    def is_configured(self) -> bool:
        """Check if credentials are configured."""
        return bool(self._client_id and self._client_secret and self._refresh_token)
    
    @property
    def token_expires_in(self) -> int:
        """Seconds until token expires (or 0 if expired/not set)."""
        if self._token_expires_at == 0:
            return 0
        remaining = int(self._token_expires_at - time.time())
        return max(0, remaining)
    
    @property
    def refresh_count(self) -> int:
        """Number of times token has been refreshed."""
        return self._token_refresh_count
    
    def _is_token_valid(self) -> bool:
        """Check if current token is still valid."""
        if self._access_token is None:
            return False
        # Refresh 5 minutes before expiry
        return time.time() < (self._token_expires_at - TOKEN_EXPIRY_BUFFER_SECONDS)
    
    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid LWA access token
            
        Raises:
            LWAAuthenticationError: If token acquisition fails
        """
        if self._is_token_valid():
            return self._access_token  # type: ignore
        
        return await self._refresh_token_request()
    
    def get_access_token_sync(self) -> str:
        """Synchronous version: Get a valid access token.
        
        Uses httpx synchronous client for non-async contexts.
        
        Returns:
            Valid LWA access token
            
        Raises:
            LWAAuthenticationError: If token acquisition fails
        """
        if self._is_token_valid():
            return self._access_token  # type: ignore
        
        return self._refresh_token_request_sync()
    
    async def _refresh_token_request(self) -> str:
        """Refresh the access token using the refresh token.
        
        Returns:
            New access token
            
        Raises:
            LWAAuthenticationError: If refresh fails
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    LWA_TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )
                
                return self._handle_token_response(response)
                
        except httpx.TimeoutException:
            raise LWAAuthenticationError(
                "LWA token request timed out",
                recoverable=True,
            )
        except httpx.NetworkError as e:
            raise LWAAuthenticationError(
                f"LWA network error: {type(e).__name__}",
                recoverable=True,
            )
        except Exception as e:
            if isinstance(e, LWAAuthenticationError):
                raise
            raise LWAAuthenticationError(
                f"Unexpected error during LWA token refresh: {type(e).__name__}",
                recoverable=True,
            )
    
    def _refresh_token_request_sync(self) -> str:
        """Synchronous refresh of the access token.
        
        Returns:
            New access token
            
        Raises:
            LWAAuthenticationError: If refresh fails
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(
                    LWA_TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )
                
                return self._handle_token_response(response)
                
        except httpx.TimeoutException:
            raise LWAAuthenticationError(
                "LWA token request timed out",
                recoverable=True,
            )
        except httpx.NetworkError as e:
            raise LWAAuthenticationError(
                f"LWA network error: {type(e).__name__}",
                recoverable=True,
            )
        except Exception as e:
            if isinstance(e, LWAAuthenticationError):
                raise
            raise LWAAuthenticationError(
                f"Unexpected error during LWA token refresh: {type(e).__name__}",
                recoverable=True,
            )
    
    def _handle_token_response(self, response: httpx.Response) -> str:
        """Process token response and update cache.
        
        Args:
            response: HTTP response from LWA endpoint
            
        Returns:
            Access token
            
        Raises:
            LWAAuthenticationError: If response indicates failure
        """
        if response.status_code == 200:
            body = response.json()
            self._access_token = body.get("access_token")
            expires_in = body.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS)
            self._token_expires_at = time.time() + expires_in
            self._token_type = body.get("token_type", "bearer")
            self._token_refresh_count += 1
            self._last_refresh_at = time.time()
            
            logger.info(
                "LWA token refreshed successfully (expires_in=%d, refresh_count=%d)",
                expires_in,
                self._token_refresh_count,
            )
            
            if not self._access_token:
                raise LWAAuthenticationError(
                    "LWA response missing access_token",
                    recoverable=False,
                )
            
            return self._access_token
        
        # Handle error responses
        try:
            body = response.json()
            error = body.get("error", "unknown")
            error_description = body.get("error_description", "No description")
        except Exception:
            error = "parse_error"
            error_description = response.text[:200]
        
        # Map specific errors
        if error == "invalid_client":
            raise LWAAuthenticationError(
                "LWA authentication failed: invalid client credentials",
                recoverable=False,
            )
        elif error == "invalid_grant":
            raise LWAAuthenticationError(
                "LWA authentication failed: refresh token is invalid or revoked",
                recoverable=False,
            )
        elif error == "unauthorized_client":
            raise LWAAuthenticationError(
                "LWA authentication failed: unauthorized client",
                recoverable=False,
            )
        elif response.status_code == 429:
            raise LWAAuthenticationError(
                "LWA rate limited — try again later",
                recoverable=True,
            )
        elif response.status_code >= 500:
            raise LWAAuthenticationError(
                f"LWA server error ({response.status_code})",
                recoverable=True,
            )
        else:
            raise LWAAuthenticationError(
                f"LWA authentication failed: {error} — {error_description}",
                recoverable=False,
            )
    
    def invalidate_token(self) -> None:
        """Invalidate the current token (force refresh on next request)."""
        self._access_token = None
        self._token_expires_at = 0
        logger.info("LWA access token invalidated")
    
    def clear(self) -> None:
        """Clear all token state (used by tests)."""
        self._access_token = None
        self._token_expires_at = 0
        self._token_refresh_count = 0
        self._last_refresh_at = None
        logger.info("LWA token manager cleared")


def create_lwa_token_manager_from_env() -> LWATokenManager | None:
    """Create LWA token manager from environment variables.
    
    Returns:
        LWATokenManager if all credentials are set, None otherwise
        
    Environment Variables:
        AMAZON_LWA_CLIENT_ID: Amazon SP-API client ID
        AMAZON_LWA_CLIENT_SECRET: Amazon SP-API client secret
        AMAZON_LWA_REFRESH_TOKEN: LWA refresh token
    """
    import os
    
    client_id = os.getenv("AMAZON_LWA_CLIENT_ID", "")
    client_secret = os.getenv("AMAZON_LWA_CLIENT_SECRET", "")
    refresh_token = os.getenv("AMAZON_LWA_REFRESH_TOKEN", "")
    
    if not all([client_id, client_secret, refresh_token]):
        logger.info("Amazon LWA credentials not configured — sandbox mode (no live Amazon connection)")
        return None
    
    try:
        manager = LWATokenManager(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
        )
        logger.info("LWA token manager created from environment")
        return manager
    except LWAAuthenticationError as e:
        logger.warning("Failed to create LWA token manager: %s", e.message)
        return None
