"""Application status schema.

Provides the response model for the GET /api/v1/status endpoint.
Inherits the generic StatusResponse so the wire contract stays
exactly {"status": "ok"}. Future chunks may extend this class
with additional metadata without breaking that contract.
"""

from app.schemas.common import StatusResponse


class AppStatus(StatusResponse):
    """Application-level status returned by GET /api/v1/status."""
