"""Amazon Product Advertising API (PA-API v5) pricing provider.

Real integration — GetItems operation, giving price, availability, and
title for an ASIN. Unlike SP-API, PA-API has no sandbox: every call here is
a live request against a real Amazon Associates account, which is why this
provider is gated behind AMAZON_PA_API_ENABLED (see app/core/config.py) in
addition to needing real credentials — enabling it is a deliberate,
explicit choice, not a side effect of setting credentials.

ELIGIBILITY CAVEAT (real and binding, not a formality): PA-API access
requires an approved Amazon Associates (affiliate) account, and Amazon can
suspend API access for accounts that don't generate qualifying sales
volume within a rolling window. This provider does not — and cannot —
verify eligibility beyond "the request succeeded or it didn't"; a 401/403
from Amazon surfaces as PricingProviderRequestError like any other failure.

VERIFICATION STATUS: the request-signing implementation below follows
Amazon's documented Product Advertising API 5.0 SigV4 signing process
(https://webservices.amazon.com/paapi5/documentation/) exactly, but has
never been exercised against the real API in this session — no
credentials or an approved Associates account were available to test
against. Treat it the same way this repo already treats
services/providers/tiktok/api_client.py's unverified endpoint paths: safe
to ship (it never runs without AMAZON_PA_API_ENABLED=true and real
credentials, and it fails loudly rather than fabricating data on a
malformed/unexpected response), but re-verify against a real account
before relying on it in production.
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.providers.pricing_base import (
    PricingProviderBase,
    PricingProviderNotConfiguredError,
    PricingProviderRequestError,
)

logger = logging.getLogger(__name__)

SERVICE = "ProductAdvertisingAPI"
GET_ITEMS_PATH = "/paapi5/getitems"
GET_ITEMS_TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"

DEFAULT_RATE_LIMIT_PER_SECOND = 1
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5

USER_AGENT = "AmazonAIFulfillmentAgent-PAAPIPricingProvider/0.1.0"


class _SigV4Signer:
    """AWS Signature Version 4 signer for PA-API 5.0 requests.

    PA-API requires SigV4 (the same scheme SP-API/most AWS services use)
    but is NOT an SP-API/general-AWS-API endpoint — it has its own host,
    service name ("ProductAdvertisingAPI"), and a fixed x-amz-target header
    per operation. Implemented by hand (hashlib/hmac, stdlib only) rather
    than pulling in boto3, matching this repo's existing preference for
    lightweight httpx-based clients (see sp_api_client.py) over heavy SDKs.
    """

    def __init__(self, access_key: str, secret_key: str, region: str, host: str):
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._host = host

    def _signing_key(self, date_stamp: str) -> bytes:
        def _hmac(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = _hmac(f"AWS4{self._secret_key}".encode("utf-8"), date_stamp)
        k_region = _hmac(k_date, self._region)
        k_service = _hmac(k_region, SERVICE)
        return _hmac(k_service, "aws4_request")

    def sign(self, path: str, payload: str, target: str) -> dict[str, str]:
        """Return the full header set (including Authorization) for a
        signed POST request with this JSON payload."""
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        headers_to_sign = {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": self._host,
            "x-amz-date": amz_date,
            "x-amz-target": target,
        }
        signed_header_names = ";".join(sorted(headers_to_sign.keys()))
        canonical_headers = "".join(
            f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items())
        )
        canonical_request = "\n".join(
            ["POST", path, "", canonical_headers, signed_header_names, payload_hash]
        )

        credential_scope = f"{date_stamp}/{self._region}/{SERVICE}/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        signing_key = self._signing_key(date_stamp)
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self._access_key}/{credential_scope}, "
            f"SignedHeaders={signed_header_names}, Signature={signature}"
        )

        return {
            **headers_to_sign,
            "authorization": authorization,
            "user-agent": USER_AGENT,
        }


class PAAPIPricingProvider(PricingProviderBase):
    """Real Amazon Product Advertising API (v5) pricing provider.

    SAFETY:
    - Only active when AMAZON_PA_API_ENABLED=true AND credentials are
      present (is_configured checks both) — enabling PA-API is a distinct,
      explicit choice from merely having credentials configured.
    - Never fabricates a price/availability/title on a malformed or
      unexpected response — raises PricingProviderRequestError instead.
    - Credentials are never logged.
    """

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        partner_tag: str | None = None,
        partner_type: str | None = None,
        marketplace: str | None = None,
        region: str | None = None,
        host: str | None = None,
        enabled: bool | None = None,
    ):
        from app.core.config import settings

        self._access_key = access_key if access_key is not None else settings.AMAZON_PA_API_ACCESS_KEY
        self._secret_key = secret_key if secret_key is not None else settings.AMAZON_PA_API_SECRET_KEY
        self._partner_tag = partner_tag if partner_tag is not None else settings.AMAZON_PA_API_PARTNER_TAG
        self._partner_type = partner_type if partner_type is not None else settings.AMAZON_PA_API_PARTNER_TYPE
        self._marketplace = marketplace if marketplace is not None else settings.AMAZON_PA_API_MARKETPLACE
        self._region = region if region is not None else settings.AMAZON_PA_API_REGION
        self._host = host if host is not None else settings.AMAZON_PA_API_HOST
        self._enabled = enabled if enabled is not None else settings.AMAZON_PA_API_ENABLED

        self._signer = (
            _SigV4Signer(self._access_key, self._secret_key, self._region, self._host)
            if self.is_configured
            else None
        )

        self._last_request_time: float = 0.0

    @property
    def provider_name(self) -> str:
        return "pa_api_pricing_provider"

    @property
    def is_configured(self) -> bool:
        return bool(
            self._enabled
            and self._access_key
            and self._secret_key
            and self._partner_tag
        )

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise PricingProviderNotConfiguredError(self.provider_name)

    def _enforce_rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = 1.0 / DEFAULT_RATE_LIMIT_PER_SECOND
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _get_item(self, asin: str) -> dict[str, Any]:
        """Call GetItems for one ASIN and return the raw item payload.

        Raises PricingProviderNotConfiguredError / PricingProviderRequestError.
        Never returns fabricated data.
        """
        self._require_configured()

        payload = json.dumps(
            {
                "ItemIds": [asin],
                "Resources": [
                    "ItemInfo.Title",
                    "Offers.Listings.Price",
                    "Offers.Listings.Availability.Message",
                ],
                "PartnerTag": self._partner_tag,
                "PartnerType": self._partner_type,
                "Marketplace": self._marketplace,
            }
        )
        headers = self._signer.sign(GET_ITEMS_PATH, payload, GET_ITEMS_TARGET)  # type: ignore[union-attr]
        url = f"https://{self._host}{GET_ITEMS_PATH}"

        last_error: PricingProviderRequestError | None = None
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            self._enforce_rate_limit()
            try:
                with httpx.Client() as client:
                    response = client.post(url, headers=headers, content=payload, timeout=30.0)
                return self._handle_response(response, asin)
            except httpx.TimeoutException:
                last_error = PricingProviderRequestError("PA-API request timed out", recoverable=True)
            except httpx.NetworkError as e:
                last_error = PricingProviderRequestError(
                    f"PA-API network error: {type(e).__name__}", recoverable=True
                )
            except PricingProviderRequestError as e:
                if not e.recoverable or attempt == MAX_RETRY_ATTEMPTS:
                    raise
                last_error = e

            logger.warning(
                "PA-API request failed (attempt %d/%d, recoverable) for ASIN %s — retrying",
                attempt, MAX_RETRY_ATTEMPTS, asin,
            )
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        raise last_error  # pragma: no cover — loop always returns or raises above

    def _handle_response(self, response: httpx.Response, asin: str) -> dict[str, Any]:
        if response.status_code != 200:
            recoverable = response.status_code == 429 or response.status_code >= 500
            raise PricingProviderRequestError(
                f"PA-API returned HTTP {response.status_code} for ASIN {asin}: {response.text[:200]}",
                recoverable=recoverable,
            )
        try:
            body = response.json()
        except Exception as e:
            raise PricingProviderRequestError(
                f"PA-API response was not valid JSON: {type(e).__name__}", recoverable=False
            ) from e

        errors = body.get("Errors")
        if errors:
            first = errors[0] if isinstance(errors, list) and errors else {}
            raise PricingProviderRequestError(
                f"PA-API error for ASIN {asin}: {first.get('Message', 'Unknown error')}",
                recoverable=False,
            )

        items = body.get("ItemsResult", {}).get("Items", [])
        if not items:
            raise PricingProviderRequestError(f"PA-API returned no item for ASIN {asin}", recoverable=False)
        return items[0]

    # -----------------------------------------------------------------------
    # PricingProviderBase
    # -----------------------------------------------------------------------

    def get_price(self, asin: str) -> dict:
        item = self._get_item(asin)
        try:
            listing = item["Offers"]["Listings"][0]
            price = listing["Price"]["Amount"]
            currency = listing["Price"].get("Currency", "USD")
        except (KeyError, IndexError, TypeError) as e:
            raise PricingProviderRequestError(
                f"PA-API response for ASIN {asin} had no usable price/offer data "
                f"({type(e).__name__}) — refusing to fabricate one",
                recoverable=False,
            ) from e
        return {
            "asin": asin,
            "price": float(price),
            "currency": currency,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }

    def get_inventory_status(self, asin: str) -> dict:
        item = self._get_item(asin)
        try:
            listing = item["Offers"]["Listings"][0]
            message = listing.get("Availability", {}).get("Message", "")
        except (KeyError, IndexError, TypeError) as e:
            raise PricingProviderRequestError(
                f"PA-API response for ASIN {asin} had no usable availability data "
                f"({type(e).__name__}) — refusing to fabricate one",
                recoverable=False,
            ) from e
        in_stock = "in stock" in message.lower() if message else False
        return {
            "asin": asin,
            "in_stock": in_stock,
            # PA-API does not expose an exact stock count — never invent one.
            "available_quantity": None,
            "availability_message": message,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }

    def get_product_details(self, asin: str) -> dict:
        item = self._get_item(asin)
        try:
            title = item["ItemInfo"]["Title"]["DisplayValue"]
        except (KeyError, TypeError) as e:
            raise PricingProviderRequestError(
                f"PA-API response for ASIN {asin} had no usable title data "
                f"({type(e).__name__}) — refusing to fabricate one",
                recoverable=False,
            ) from e
        return {
            "asin": asin,
            "title": title,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }
