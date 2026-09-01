"""SKU + variation mapping engine.

Resolves a TikTok SKU + variation to an Amazon SKU/ASIN. Binding safety
rule: a fuzzy match is never trusted as a production mapping — only an
explicitly human-confirmed mapping can ever resolve to a real Amazon SKU
for fulfillment. See engine.py and docs/tiktok-integration.md.
"""
