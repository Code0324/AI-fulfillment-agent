"""Security utilities for PII protection and secret redaction.

Provides functions to safely handle sensitive data in logs and output.
No real customer PII is processed — all test data is synthetic.
"""

import re


def redact_pii(text: str) -> str:
    """Redact personally identifiable information from text.

    Redacts:
    - Phone numbers (US format)
    - Postal/ZIP codes
    - Email addresses

    Args:
        text: Text potentially containing PII.

    Returns:
        Text with PII replaced by redaction markers.
    """
    if not text:
        return text

    # Redact phone numbers (various formats)
    text = re.sub(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "[PHONE REDACTED]",
        text,
    )

    # Redact ZIP codes (5-digit or ZIP+4)
    text = re.sub(r"\b\d{5}(?:-\d{4})?\b", "[ZIP REDACTED]", text)

    # Redact email addresses
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "[EMAIL REDACTED]",
        text,
    )

    return text


def redact_secret(value: str, visible_chars: int = 4) -> str:
    """Redact a secret value, showing only the last few characters.

    Args:
        value: The secret value to redact.
        visible_chars: Number of trailing characters to show.

    Returns:
        Redacted string like '***abc1'.
    """
    if not value or len(value) <= visible_chars:
        return "***"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def safe_log_address(address: str) -> str:
    """Create a safe version of an address for logging.

    Shows only the first line (city/state) and redacts detailed PII.

    Args:
        address: Full address string.

    Returns:
        Partially redacted address safe for logs.
    """
    if not address:
        return "[NO ADDRESS]"

    lines = [line.strip() for line in address.split("\n") if line.strip()]

    if len(lines) <= 1:
        return redact_pii(address)

    # Show only city/state line if available, redact the rest
    city_line = lines[-2] if len(lines) >= 2 else lines[-1]
    return f"[REDACTED] / {redact_pii(city_line)}"
