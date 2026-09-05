"""Pricing provider tests.

No real Amazon PA-API calls, no real scraping of amazon.com — the PA-API
signer is verified offline against AWS's documented SigV4 shape (this repo
has no approved Associates account to test a real request against — see
pa_api_pricing.py's module docstring), and the scrape provider's HTML
parsing is verified against static fixture strings, never a live fetch.
"""

import pytest

from app.core.config import settings
from app.services.providers.amazon.pa_api_pricing import PAAPIPricingProvider, _SigV4Signer
from app.services.providers.amazon.scrape_pricing import ScrapePricingProvider
from app.services.providers.mock.mock_pricing import MockPricingProvider
from app.services.providers.pricing_base import (
    PricingProviderNotConfiguredError,
    PricingProviderRequestError,
)
from app.services.providers.registry import ProviderRegistry, create_default_registry


# ===========================================================================
# MockPricingProvider
# ===========================================================================


class TestMockPricingProvider:
    def test_is_configured(self):
        assert MockPricingProvider().is_configured is True

    def test_get_price_is_deterministic_for_the_same_asin(self):
        provider = MockPricingProvider()
        r1 = provider.get_price("B0SOMERANDOMASIN")
        r2 = provider.get_price("B0SOMERANDOMASIN")
        assert r1["price"] == r2["price"]

    def test_known_fixture_asin_returns_its_exact_price(self):
        provider = MockPricingProvider()
        result = provider.get_price("B0MOCKASIN01")
        assert result["price"] == 19.99
        assert result["currency"] == "USD"
        assert result["asin"] == "B0MOCKASIN01"
        assert result["source"] == "mock_pricing_provider"

    def test_get_inventory_status_shape(self):
        provider = MockPricingProvider()
        result = provider.get_inventory_status("B0MOCKASIN03")
        assert result["in_stock"] is False
        assert result["available_quantity"] == 0

    def test_get_product_details_shape(self):
        provider = MockPricingProvider()
        result = provider.get_product_details("B0MOCKASIN02")
        assert result["title"] == "Synthetic Widget Beta"

    def test_unknown_asin_still_returns_a_result_never_raises(self):
        """Every ASIN is deterministically "known" to the mock provider —
        it never raises PricingProviderRequestError, unlike a real provider
        for a genuinely unlisted ASIN."""
        provider = MockPricingProvider()
        result = provider.get_price("B0TOTALLYUNKNOWN99")
        assert isinstance(result["price"], float)
        assert result["price"] > 0


# ===========================================================================
# PAAPIPricingProvider — never configured in tests (no real credentials)
# ===========================================================================


class TestPAAPIPricingProviderNotConfigured:
    def test_not_configured_when_disabled(self):
        assert PAAPIPricingProvider(enabled=False).is_configured is False

    def test_not_configured_without_all_credentials(self):
        provider = PAAPIPricingProvider(
            enabled=True, access_key="a", secret_key="", partner_tag="t"
        )
        assert provider.is_configured is False

    def test_configured_requires_enabled_flag_even_with_full_credentials(self):
        """AMAZON_PA_API_ENABLED is a separate, explicit gate from merely
        having credentials — this is a deliberate design requirement, not
        an accident of implementation."""
        provider = PAAPIPricingProvider(
            enabled=False, access_key="a", secret_key="b", partner_tag="t"
        )
        assert provider.is_configured is False

    @pytest.mark.parametrize("method", ["get_price", "get_inventory_status", "get_product_details"])
    def test_every_method_raises_not_configured(self, method):
        provider = PAAPIPricingProvider(enabled=False)
        with pytest.raises(PricingProviderNotConfiguredError):
            getattr(provider, method)("B0TEST")

    def test_never_constructs_an_http_client_when_not_configured(self, monkeypatch):
        """Guards against a future refactor accidentally making a network
        call before the configuration check."""
        import httpx

        def _boom(*a, **k):
            raise AssertionError("must not construct an HTTP client when unconfigured")

        monkeypatch.setattr(httpx, "Client", _boom)
        with pytest.raises(PricingProviderNotConfiguredError):
            PAAPIPricingProvider(enabled=False).get_price("B0TEST")


class TestSigV4Signer:
    """Offline verification that the signer follows AWS SigV4's documented
    structure — not a live-request test (see class docstring above)."""

    def test_produces_well_formed_authorization_header(self):
        signer = _SigV4Signer(
            access_key="AKIDEXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            region="us-east-1",
            host="webservices.amazon.com",
        )
        headers = signer.sign(
            "/paapi5/getitems",
            '{"ItemIds":["B0TEST"]}',
            "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
        )
        auth = headers["authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
        assert "/us-east-1/ProductAdvertisingAPI/aws4_request" in auth
        assert "SignedHeaders=" in auth
        signature = auth.rsplit("Signature=", 1)[1]
        assert len(signature) == 64  # sha256 hex digest length
        assert all(c in "0123456789abcdef" for c in signature)
        assert headers["x-amz-target"] == "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"

    def test_signature_changes_with_payload(self):
        """Sanity check that the signature is actually derived from the
        request content, not a constant."""
        signer = _SigV4Signer(
            access_key="AKIDEXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            region="us-east-1",
            host="webservices.amazon.com",
        )
        target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"
        sig1 = signer.sign("/paapi5/getitems", '{"ItemIds":["A"]}', target)["authorization"]
        sig2 = signer.sign("/paapi5/getitems", '{"ItemIds":["B"]}', target)["authorization"]
        assert sig1 != sig2


# ===========================================================================
# ScrapePricingProvider — never fetches a real page in tests
# ===========================================================================


class TestScrapePricingProviderNotConfigured:
    def test_not_configured_by_default(self):
        assert ScrapePricingProvider(enabled=False).is_configured is False

    @pytest.mark.parametrize("method", ["get_price", "get_inventory_status", "get_product_details"])
    def test_every_method_raises_not_configured(self, method):
        provider = ScrapePricingProvider(enabled=False)
        with pytest.raises(PricingProviderNotConfiguredError):
            getattr(provider, method)("B0TEST")

    def test_never_fetches_when_not_configured(self, monkeypatch):
        import httpx

        def _boom(*a, **k):
            raise AssertionError("must not construct an HTTP client when unconfigured")

        monkeypatch.setattr(httpx, "Client", _boom)
        with pytest.raises(PricingProviderNotConfiguredError):
            ScrapePricingProvider(enabled=False).get_price("B0TEST")


class TestScrapePricingProviderParsing:
    """HTML-parsing logic only, against static fixture strings — this
    deliberately never fetches a real Amazon page (see
    scrape_pricing.py's module docstring for why an automated test suite
    must not do that)."""

    def test_parses_price_from_fixture_html(self, monkeypatch):
        provider = ScrapePricingProvider(enabled=True)
        html = '<span class="a-offscreen">$1,234.56</span>'
        monkeypatch.setattr(provider, "_fetch_page", lambda asin: html)
        result = provider.get_price("B0TEST")
        assert result["price"] == 1234.56
        assert result["currency"] == "USD"

    def test_raises_rather_than_fabricating_when_price_not_found(self, monkeypatch):
        provider = ScrapePricingProvider(enabled=True)
        monkeypatch.setattr(provider, "_fetch_page", lambda asin: "<html>no price here</html>")
        with pytest.raises(PricingProviderRequestError):
            provider.get_price("B0TEST")

    def test_parses_title_from_fixture_html(self, monkeypatch):
        provider = ScrapePricingProvider(enabled=True)
        html = '<span id="productTitle" class="a-size-large">  Test Widget  </span>'
        monkeypatch.setattr(provider, "_fetch_page", lambda asin: html)
        result = provider.get_product_details("B0TEST")
        assert result["title"] == "Test Widget"

    def test_raises_rather_than_fabricating_when_title_not_found(self, monkeypatch):
        provider = ScrapePricingProvider(enabled=True)
        monkeypatch.setattr(provider, "_fetch_page", lambda asin: "<html></html>")
        with pytest.raises(PricingProviderRequestError):
            provider.get_product_details("B0TEST")

    def test_in_stock_when_availability_message_is_positive(self, monkeypatch):
        provider = ScrapePricingProvider(enabled=True)
        html = '<div id="availability"><span class="a-size-medium">In Stock.</span></div>'
        monkeypatch.setattr(provider, "_fetch_page", lambda asin: html)
        result = provider.get_inventory_status("B0TEST")
        assert result["in_stock"] is True

    def test_out_of_stock_when_availability_message_says_so(self, monkeypatch):
        provider = ScrapePricingProvider(enabled=True)
        html = '<div id="availability"><span class="a-size-medium">Currently unavailable.</span></div>'
        monkeypatch.setattr(provider, "_fetch_page", lambda asin: html)
        result = provider.get_inventory_status("B0TEST")
        assert result["in_stock"] is False

    def test_in_stock_is_unknown_not_guessed_true_when_no_availability_element(self, monkeypatch):
        """Absence of a matched element must never be silently treated as
        "in stock" — that would be exactly the kind of fabrication this
        provider's module docstring says it must not do."""
        provider = ScrapePricingProvider(enabled=True)
        monkeypatch.setattr(provider, "_fetch_page", lambda asin: "<html></html>")
        result = provider.get_inventory_status("B0TEST")
        assert result["in_stock"] is None


# ===========================================================================
# Registry provider selection
# ===========================================================================


class TestRegistryPricingProviderSelection:
    def test_defaults_to_mock(self, monkeypatch):
        monkeypatch.setattr(settings, "PRICING_PROVIDER", "mock")
        registry = create_default_registry()
        assert registry.get_pricing_provider().provider_name == "mock_pricing_provider"

    def test_selects_pa_api(self, monkeypatch):
        monkeypatch.setattr(settings, "PRICING_PROVIDER", "pa_api")
        registry = create_default_registry()
        assert registry.get_pricing_provider().provider_name == "pa_api_pricing_provider"

    def test_selects_scrape(self, monkeypatch):
        monkeypatch.setattr(settings, "PRICING_PROVIDER", "scrape")
        registry = create_default_registry()
        assert registry.get_pricing_provider().provider_name == "scrape_pricing_provider"

    def test_unrecognized_value_falls_back_to_mock_rather_than_raising(self, monkeypatch):
        monkeypatch.setattr(settings, "PRICING_PROVIDER", "bogus_value")
        registry = create_default_registry()
        assert registry.get_pricing_provider().provider_name == "mock_pricing_provider"

    def test_get_pricing_provider_without_one_set_raises(self):
        registry = ProviderRegistry()
        with pytest.raises(RuntimeError):
            registry.get_pricing_provider()

    def test_only_one_pricing_provider_is_ever_active(self, monkeypatch):
        monkeypatch.setattr(settings, "PRICING_PROVIDER", "mock")
        registry = create_default_registry()
        first = registry.get_pricing_provider()
        registry.set_pricing_provider(MockPricingProvider())
        second = registry.get_pricing_provider()
        assert first is not second  # the *new* one replaced it entirely
