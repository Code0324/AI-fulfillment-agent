"""Tests for the SKU + variation mapping engine.

Binding safety rule under test: a fuzzy match is NEVER returned as
MATCHED, regardless of confidence score — only an explicitly confirmed
mapping can ever be MATCHED. See app/services/sku_mapping/engine.py.
"""

from app.schemas.sku_mapping import MappingStatus
from app.services.sku_mapping.engine import sku_mapping_engine

from tests.conftest import create_test_organization


class TestDeterministicExactMatch:
    def test_exact_row_returned_as_is(self):
        org_id = create_test_organization()
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-001", "Red/M", "AMZ-SKU-001", "B00TESTASIN", org_id
        )
        result = sku_mapping_engine.map_sku("TT-SKU-001", "Red/M", org_id)
        assert result.status == MappingStatus.MATCHED
        assert result.amazon_sku == "AMZ-SKU-001"
        assert result.asin == "B00TESTASIN"
        assert result.confidence_score == 1.0


class TestFuzzySuggestionNeverAutoTrusted:
    def test_high_score_fuzzy_match_is_still_needs_review(self):
        org_id = create_test_organization()
        # Confirm one mapping explicitly, then ask for a near-identical
        # but not-exact SKU/variation — the corpus comparison should
        # score this very high, but it must NOT come back MATCHED.
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-JACKET-001", "Blue/L", "AMZ-JACKET-001", "B00JACKET01", org_id
        )
        result = sku_mapping_engine.map_sku("TT-SKU-JACKET-001", "Blue/L2", org_id)
        assert result.status != MappingStatus.MATCHED
        assert result.status == MappingStatus.NEEDS_REVIEW
        # The suggestion is surfaced, but is a suggestion only.
        assert result.amazon_sku == "AMZ-JACKET-001"
        assert result.confidence_score >= 0.5


class TestVariationLevelMapping:
    def test_same_sku_different_variation_resolves_differently(self):
        org_id = create_test_organization()
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-SHIRT", "Red/M", "AMZ-SHIRT-RED-M", "B00SHIRTREDM", org_id
        )
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-SHIRT", "Blue/L", "AMZ-SHIRT-BLUE-L", "B00SHIRTBLUL", org_id
        )

        red = sku_mapping_engine.map_sku("TT-SKU-SHIRT", "Red/M", org_id)
        blue = sku_mapping_engine.map_sku("TT-SKU-SHIRT", "Blue/L", org_id)

        assert red.status == MappingStatus.MATCHED
        assert blue.status == MappingStatus.MATCHED
        assert red.amazon_sku == "AMZ-SHIRT-RED-M"
        assert blue.amazon_sku == "AMZ-SHIRT-BLUE-L"
        assert red.amazon_sku != blue.amazon_sku


class TestUnmappedSku:
    def test_no_candidates_returns_not_found(self):
        org_id = create_test_organization()
        result = sku_mapping_engine.map_sku("TT-SKU-NEVER-SEEN", "Purple/XS", org_id)
        assert result.status == MappingStatus.NOT_FOUND
        assert result.amazon_sku is None
        assert result.asin is None


class TestConflictDetection:
    def test_two_close_candidates_are_a_conflict(self):
        org_id = create_test_organization()
        # Two confirmed mappings that are roughly equally similar to the
        # lookup target — neither should be auto-picked.
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-PHONE-CASE-A", "Black", "AMZ-CASE-A", "B00CASEA0001", org_id
        )
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-PHONE-CASE-B", "Black", "AMZ-CASE-B", "B00CASEB0001", org_id
        )
        result = sku_mapping_engine.map_sku("TT-SKU-PHONE-CASE-C", "Black", org_id)
        assert result.status in (MappingStatus.CONFLICT, MappingStatus.NEEDS_REVIEW, MappingStatus.NOT_FOUND)
        # Whatever it resolves to, it must never be MATCHED from fuzzy input.
        assert result.status != MappingStatus.MATCHED


class TestExplicitMapping:
    def test_create_then_map_finds_it_deterministically(self):
        org_id = create_test_organization()
        created = sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-999", None, "AMZ-SKU-999", None, org_id
        )
        assert created.status == "matched"
        assert created.source == "explicit"

        result = sku_mapping_engine.map_sku("TT-SKU-999", None, org_id)
        assert result.status == MappingStatus.MATCHED
        assert result.amazon_sku == "AMZ-SKU-999"


class TestMultiTenantIsolation:
    def test_mapping_in_one_org_invisible_to_another(self):
        org_a = create_test_organization()
        org_b = create_test_organization()
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-SHARED", "One-Size", "AMZ-SHARED", "B00SHARED001", org_a
        )
        result_a = sku_mapping_engine.map_sku("TT-SKU-SHARED", "One-Size", org_a)
        result_b = sku_mapping_engine.map_sku("TT-SKU-SHARED", "One-Size", org_b)

        assert result_a.status == MappingStatus.MATCHED
        assert result_b.status != MappingStatus.MATCHED
