"""Address processor abstraction and mock implementation.

Provides a replaceable processor interface for address normalization.
The MockAddressProcessor uses deterministic rules for testing without
external AI dependencies.

All test data is synthetic — no real customer PII is used.
"""

import re
from abc import ABC, abstractmethod

from app.schemas.address import (
    AddressProcessingStatus,
    AddressProcessingResult,
    ValidationIssue,
    ValidationSeverity,
)


# ---------------------------------------------------------------------------
# Country normalization map
# ---------------------------------------------------------------------------

COUNTRY_MAP: dict[str, str] = {
    "united states": "US",
    "usa": "US",
    "us": "US",
    "united kingdom": "UK",
    "uk": "UK",
    "great britain": "UK",
    "canada": "CA",
    "ca": "CA",
    "australia": "AU",
    "au": "AU",
    "germany": "DE",
    "de": "DE",
    "france": "FR",
    "fr": "FR",
    "japan": "JP",
    "jp": "JP",
    "china": "CN",
    "cn": "CN",
    "india": "IN",
    "in": "IN",
    "brazil": "BR",
    "br": "BR",
    "mexico": "MX",
    "mx": "MX",
}

# Common US state abbreviations
US_STATES: set[str] = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}


# ---------------------------------------------------------------------------
# Abstract processor
# ---------------------------------------------------------------------------

class AddressProcessor(ABC):
    """Abstract base class for address processors.

    Implementations accept a raw address string and return a structured
    processing result with normalized fields and validation issues.
    """

    @abstractmethod
    def process(self, raw_address: str) -> AddressProcessingResult:
        """Process a raw address string into structured fields.

        Args:
            raw_address: The raw address text to process.

        Returns:
            AddressProcessingResult with normalized fields, status,
            confidence, and any validation issues.
        """
        ...


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _normalize_country(country: str) -> str:
    """Normalize country name to standard 2-letter code."""
    cleaned = country.strip()
    lower = cleaned.lower()
    if lower in COUNTRY_MAP:
        return COUNTRY_MAP[lower]
    if len(cleaned) == 2 and cleaned.upper() in {v for v in COUNTRY_MAP.values()}:
        return cleaned.upper()
    return cleaned.upper() if len(cleaned) <= 2 else cleaned


def _normalize_state(state: str) -> str:
    """Normalize state abbreviation."""
    cleaned = state.strip().upper()
    if cleaned in US_STATES:
        return cleaned
    return state.strip()


def _normalize_phone(phone: str) -> str:
    """Normalize phone number to digits with dashes."""
    digits = re.sub(r"[^0-9]", "", phone)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"+1-{digits[1:4]}-{digits[4:7]}-{digits[7:]}"
    return phone.strip()


def _redact_pii(text: str) -> str:
    """Redact sensitive information from text for safe logging."""
    # Redact phone numbers
    text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE REDACTED]", text)
    # Redact postal codes
    text = re.sub(r"\b\d{5}(?:-\d{4})?\b", "[ZIP REDACTED]", text)
    return text


# ---------------------------------------------------------------------------
# Mock processor
# ---------------------------------------------------------------------------

class MockAddressProcessor(AddressProcessor):
    """Deterministic address processor for testing.

    Uses rule-based parsing to extract address fields from raw text.
    No external AI or LLM dependencies.
    """

    def process(self, raw_address: str) -> AddressProcessingResult:
        """Process a raw address using deterministic rules."""
        from uuid import uuid4
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result_id = uuid4()

        # Initialize empty result
        result = AddressProcessingResult(
            id=result_id,
            raw_address=raw_address,
            created_at=now,
            updated_at=now,
        )

        if not raw_address or not raw_address.strip():
            result.status = AddressProcessingStatus.FAILED
            result.review_reason = "Empty address input"
            result.validation_issues.append(
                ValidationIssue(
                    field="raw_address",
                    message="Address input is empty",
                    severity=ValidationSeverity.ERROR,
                )
            )
            return result

        # Split into lines
        lines = [line.strip() for line in raw_address.strip().split("\n") if line.strip()]

        if len(lines) < 2:
            result.status = AddressProcessingStatus.FAILED
            result.review_reason = "Address too short — need at least name and street"
            result.validation_issues.append(
                ValidationIssue(
                    field="raw_address",
                    message="Address must have at least 2 lines (name + street)",
                    severity=ValidationSeverity.ERROR,
                )
            )
            return result

        # Parse name from first line
        name_parts = lines[0].split(None, 1)
        if len(name_parts) >= 2:
            result.first_name = name_parts[0]
            result.last_name = name_parts[1]
        elif len(name_parts) == 1:
            result.first_name = name_parts[0]
            result.review_reason = "Missing last name"
            result.validation_issues.append(
                ValidationIssue(
                    field="last_name",
                    message="Could not extract last name",
                    severity=ValidationSeverity.WARNING,
                )
            )

        # Parse address lines
        if len(lines) >= 3:
            # Check if second line is an apartment/suite indicator
            second_line = lines[1].lower()
            if any(
                keyword in second_line
                for keyword in ["apt", "suite", "ste", "unit", "#", "floor"]
            ):
                result.address_line_1 = lines[2] if len(lines) > 2 else ""
                result.address_line_2 = lines[1]
            else:
                result.address_line_1 = lines[1]
                if len(lines) > 3:
                    result.address_line_2 = lines[2]

        # Parse city, state, zip from the line after address
        city_state_zip_line = ""
        for line in lines[2:]:
            # Look for line with state abbreviation or postal code
            if re.search(r"\b\d{5}(?:-\d{4})?\b", line) or re.search(
                r"\b[A-Z]{2}\b", line
            ):
                city_state_zip_line = line
                break

        if city_state_zip_line:
            # Try to extract postal code
            zip_match = re.search(r"\b(\d{5}(?:-\d{4})?)\b", city_state_zip_line)
            if zip_match:
                result.postal_code = zip_match.group(1)

            # Try to extract state (2-letter code)
            state_match = re.search(r"\b([A-Z]{2})\b", city_state_zip_line)
            if state_match:
                state_code = state_match.group(1)
                if state_code in US_STATES:
                    result.state = state_code
                else:
                    result.state = state_code
                    result.validation_issues.append(
                        ValidationIssue(
                            field="state",
                            message=f"State '{state_code}' not recognized as US state",
                            severity=ValidationSeverity.WARNING,
                        )
                    )

            # Extract city (everything before state/zip)
            city_part = city_state_zip_line
            if state_match:
                city_part = city_part[: state_match.start()].strip()
            if zip_match and zip_match.start() < len(city_part):
                city_part = city_part[: city_part.rfind(zip_match.group(1))].strip()
            # Remove trailing comma
            city_part = city_part.rstrip(",").strip()
            if city_part:
                result.city = city_part

        # Parse country from last line if it looks like a country
        if len(lines) > 3:
            last_line = lines[-1].strip()
            if last_line.lower() in COUNTRY_MAP or len(last_line) <= 3:
                result.country = _normalize_country(last_line)

        # Parse phone if found anywhere
        for line in lines:
            phone_match = re.search(
                r"\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b", line
            )
            if phone_match:
                result.phone = _normalize_phone(phone_match.group(1))
                break

        # Add validation warnings for missing required fields
        if not result.postal_code:
            result.validation_issues.append(
                ValidationIssue(
                    field="postal_code",
                    message="Postal/ZIP code is missing",
                    severity=ValidationSeverity.WARNING,
                )
            )
        if not result.city:
            result.validation_issues.append(
                ValidationIssue(
                    field="city",
                    message="City is missing",
                    severity=ValidationSeverity.WARNING,
                )
            )
        if not result.state:
            result.validation_issues.append(
                ValidationIssue(
                    field="state",
                    message="State/province is missing",
                    severity=ValidationSeverity.WARNING,
                )
            )
        if not result.country:
            result.validation_issues.append(
                ValidationIssue(
                    field="country",
                    message="Country is missing",
                    severity=ValidationSeverity.WARNING,
                )
            )

        # Calculate confidence and status
        required_fields = [
            result.first_name,
            result.last_name,
            result.address_line_1,
            result.city,
            result.state,
            result.postal_code,
            result.country,
        ]
        filled_count = sum(1 for f in required_fields if f)
        confidence = filled_count / len(required_fields)
        result.confidence = round(confidence, 2)

        # Determine status
        errors = [
            i for i in result.validation_issues if i.severity == ValidationSeverity.ERROR
        ]
        warnings = [
            i for i in result.validation_issues if i.severity == ValidationSeverity.WARNING
        ]

        if errors:
            result.status = AddressProcessingStatus.FAILED
            result.review_reason = "Validation errors found"
        elif confidence < 0.7 or warnings:
            result.status = AddressProcessingStatus.NEEDS_REVIEW
            reasons = []
            if not result.postal_code:
                reasons.append("missing postal code")
            if not result.city:
                reasons.append("missing city")
            if not result.state:
                reasons.append("missing state")
            if warnings:
                reasons.append(f"{len(warnings)} warning(s)")
            result.review_reason = (
                "; ".join(reasons) if reasons else "Low confidence"
            )
        else:
            result.status = AddressProcessingStatus.PROCESSED

        return result
