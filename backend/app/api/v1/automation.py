"""API v1 automation routes — sandbox browser automation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query, status as http_status
from fastapi.responses import HTMLResponse

from app.core.errors import ValidationError
from app.schemas.automation import (
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
    AutomationAction,
    AutomationEnvironment,
    AutomationSession,
    FormFillRequest,
    FormFillResult,
    SessionListResponse,
)
from app.services.automation.engine import automation_engine
from app.services.automation.sandbox_page import get_sandbox_page_html

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/sandbox", response_class=HTMLResponse)
def get_sandbox_page():
    """Return the local sandbox checkout page."""
    return HTMLResponse(content=get_sandbox_page_html())


@router.post("/sessions", response_model=AutomationSession, status_code=http_status.HTTP_201_CREATED)
def create_session(
    environment: AutomationEnvironment = Query(
        default=AutomationEnvironment.SANDBOX,
        description="Automation environment (sandbox only for now)"
    ),
) -> AutomationSession:
    """Create a new automation session."""
    if environment != AutomationEnvironment.SANDBOX:
        raise ValidationError("Only sandbox environment is allowed")
    return automation_engine.create_session(environment)


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
) -> SessionListResponse:
    """List automation sessions."""
    return automation_engine.list_sessions(page=page, page_size=page_size)


@router.get("/sessions/{session_id}", response_model=AutomationSession)
def get_session(session_id: UUID) -> AutomationSession:
    """Return a single automation session."""
    return automation_engine.get_session(session_id)


@router.post("/sessions/{session_id}/stop", response_model=AutomationSession)
def stop_session(session_id: UUID) -> AutomationSession:
    """Stop an automation session."""
    return automation_engine.stop_session(session_id)


@router.post("/sessions/{session_id}/fill", response_model=FormFillResult)
def fill_form(session_id: UUID, request: FormFillRequest) -> FormFillResult:
    """Fill a form using normalized address data."""
    if request.session_id != session_id:
        raise ValidationError("Session ID in path and body must match")
    return automation_engine.fill_form(request)


@router.post("/sessions/{session_id}/approve", response_model=ApprovalRequest)
def request_approval(
    session_id: UUID,
    action: AutomationAction,
    description: str = "",
) -> ApprovalRequest:
    """Request approval for a high-risk action."""
    return automation_engine.request_approval(session_id, action, description)


@router.post("/approvals/{request_id}/respond", response_model=ApprovalRequest)
def respond_to_approval(
    request_id: UUID,
    response: ApprovalResponse,
) -> ApprovalRequest:
    """Respond to an approval request."""
    return automation_engine.respond_to_approval(request_id, response)


@router.get("/approvals/{request_id}", response_model=ApprovalRequest)
def get_approval(request_id: UUID) -> ApprovalRequest:
    """Return a single approval request."""
    return automation_engine.get_approval(request_id)
