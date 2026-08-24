"""Automation engine with approval system, audit logging, and fail-safe behavior.

Provides policy-safe automation foundation for browser-based workflows.
All actions in sandbox environment use synthetic data only.
"""

import math
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.errors import NotFoundError, ValidationError
from app.schemas.automation import (
    ACTION_RISK_MAP,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
    AuditEvent,
    AuditResult,
    AutomationAction,
    AutomationActionRisk,
    AutomationEnvironment,
    AutomationSession,
    AutomationSessionStatus,
    FormFillRequest,
    FormFillResult,
    NormalizedAddress,
    SessionListResponse,
)
from app.services.automation.browser import (
    BrowserSession,
    CaptchaDetectedError,
    MfaDetectedError,
    AuthenticationRequiredError,
    ElementNotFoundError,
    create_browser_session,
)


class AutomationEngine:
    """In-memory automation engine with approval and audit systems."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, AutomationSession] = {}
        self._approvals: dict[UUID, ApprovalRequest] = {}
        self._audit_log: list[AuditEvent] = []
        self._browser_sessions: dict[UUID, BrowserSession] = {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, environment: AutomationEnvironment = AutomationEnvironment.SANDBOX) -> AutomationSession:
        """Create a new automation session."""
        now = datetime.now(timezone.utc)
        session = AutomationSession(
            id=uuid4(),
            environment=environment,
            status=AutomationSessionStatus.IDLE,
            created_at=now,
            updated_at=now,
        )
        self._sessions[session.id] = session

        # Create browser session
        browser = create_browser_session(environment=environment.value)
        browser.start()
        self._browser_sessions[session.id] = browser

        self._audit(session.id, AutomationAction.NAVIGATE, AuditResult.SUCCESS, "Session created")
        return session

    def get_session(self, session_id: UUID) -> AutomationSession:
        """Return one session by ID or raise NotFoundError."""
        session = self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Automation session not found")
        return session

    def list_sessions(
        self, *, page: int = 1, page_size: int = 10
    ) -> SessionListResponse:
        """Return a paginated slice of sessions."""
        all_sessions = list(self._sessions.values())
        total_items = len(all_sessions)
        total_pages = math.ceil(total_items / page_size) if total_items else 0
        start = (page - 1) * page_size
        end = start + page_size
        items = all_sessions[start:end]
        return SessionListResponse(
            items=items, page=page, page_size=page_size,
            total_items=total_items, total_pages=total_pages,
        )

    def stop_session(self, session_id: UUID) -> AutomationSession:
        """Stop an automation session and cleanup browser."""
        session = self.get_session(session_id)
        browser = self._browser_sessions.get(session_id)
        if browser:
            browser.stop()
            del self._browser_sessions[session_id]

        now = datetime.now(timezone.utc)
        updated = session.model_copy(
            update={"status": AutomationSessionStatus.STOPPED, "updated_at": now}
        )
        self._sessions[session_id] = updated
        self._audit(session_id, AutomationAction.NAVIGATE, AuditResult.SUCCESS, "Session stopped")
        return updated

    # ------------------------------------------------------------------
    # Approval system
    # ------------------------------------------------------------------

    def request_approval(
        self, session_id: UUID, action: AutomationAction, description: str
    ) -> ApprovalRequest:
        """Create an approval request for a high-risk action."""
        session = self.get_session(session_id)
        risk = ACTION_RISK_MAP.get(action, AutomationActionRisk.SAFE)

        if risk == AutomationActionRisk.SAFE:
            raise ValidationError(f"Action '{action.value}' does not require approval")

        now = datetime.now(timezone.utc)
        request = ApprovalRequest(
            id=uuid4(),
            session_id=session_id,
            action=action,
            description=description,
            status=ApprovalStatus.PENDING,
            created_at=now,
        )
        self._approvals[request.id] = request

        # Update session status
        updated = session.model_copy(
            update={"status": AutomationSessionStatus.WAITING_APPROVAL, "updated_at": now}
        )
        self._sessions[session_id] = updated

        self._audit(session_id, action, AuditResult.PENDING_APPROVAL, description)
        return request

    def respond_to_approval(
        self, request_id: UUID, response: ApprovalResponse
    ) -> ApprovalRequest:
        """Respond to an approval request."""
        request = self._approvals.get(request_id)
        if request is None:
            raise NotFoundError("Approval request not found")
        if request.status != ApprovalStatus.PENDING:
            raise ValidationError("Approval request already resolved")

        now = datetime.now(timezone.utc)
        updated = request.model_copy(
            update={"status": response.status, "resolved_at": now}
        )
        self._approvals[request_id] = updated

        # Update session status
        session = self.get_session(request.session_id)
        new_status = AutomationSessionStatus.RUNNING if response.status == ApprovalStatus.APPROVED else AutomationSessionStatus.IDLE
        session_updated = session.model_copy(update={"status": new_status, "updated_at": now})
        self._sessions[request.session_id] = session_updated

        result = AuditResult.SUCCESS if response.status == ApprovalStatus.APPROVED else AuditResult.CANCELLED
        self._audit(request.session_id, request.action, result, f"Approval {response.status.value}")
        return updated

    def get_approval(self, request_id: UUID) -> ApprovalRequest:
        """Return one approval request by ID."""
        request = self._approvals.get(request_id)
        if request is None:
            raise NotFoundError("Approval request not found")
        return request

    # ------------------------------------------------------------------
    # Form fill workflow
    # ------------------------------------------------------------------

    def fill_form(self, request: FormFillRequest) -> FormFillResult:
        """Fill a form using normalized address data."""
        session = self.get_session(request.session_id)
        browser = self._browser_sessions.get(request.session_id)
        if browser is None:
            raise NotFoundError("No active browser session")

        filled_fields = []
        addr = request.address

        try:
            # Map normalized address to form fields
            field_map = {
                "#first_name": addr.first_name,
                "#last_name": addr.last_name,
                "#address1": addr.address_line_1,
                "#address2": addr.address_line_2,
                "#city": addr.city,
                "#state": addr.state,
                "#zip": addr.postal_code,
                "#country": addr.country,
                "#phone": addr.phone,
            }

            for selector, value in field_map.items():
                if value:
                    result = browser.fill_field(selector, value)
                    if result.success:
                        filled_fields.append(selector)

            # Select shipping method
            if request.shipping_method:
                browser.select_option("#shipping_method", request.shipping_method)
                filled_fields.append("#shipping_method")

            # Verify filled data
            browser.check_for_security_blocks()

            # Capture screenshot
            screenshot = browser.screenshot(f"form_fill_{session.id}")

            # Update session
            now = datetime.now(timezone.utc)
            updated = session.model_copy(
                update={
                    "status": AutomationSessionStatus.COMPLETED,
                    "current_action": "form_fill",
                    "last_result": f"Filled {len(filled_fields)} fields",
                    "updated_at": now,
                }
            )
            self._sessions[session.id] = updated

            self._audit(session.id, AutomationAction.FILL, AuditResult.SUCCESS, f"Filled {len(filled_fields)} fields")

            return FormFillResult(
                session_id=session.id,
                success=True,
                filled_fields=filled_fields,
                screenshot_path=screenshot.path if screenshot.success else None,
            )

        except (CaptchaDetectedError, MfaDetectedError, AuthenticationRequiredError) as e:
            now = datetime.now(timezone.utc)
            updated = session.model_copy(
                update={
                    "status": AutomationSessionStatus.FAILED,
                    "error_message": str(e),
                    "updated_at": now,
                }
            )
            self._sessions[session.id] = updated
            self._audit(session.id, AutomationAction.FILL, AuditResult.FAILURE, str(e))

            return FormFillResult(
                session_id=session.id,
                success=False,
                filled_fields=filled_fields,
                error_message=str(e),
            )

        except Exception as e:
            now = datetime.now(timezone.utc)
            updated = session.model_copy(
                update={
                    "status": AutomationSessionStatus.FAILED,
                    "error_message": str(e),
                    "updated_at": now,
                }
            )
            self._sessions[session.id] = updated
            self._audit(session.id, AutomationAction.FILL, AuditResult.FAILURE, str(e))

            return FormFillResult(
                session_id=session.id,
                success=False,
                filled_fields=filled_fields,
                error_message=str(e),
            )

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def get_audit_log(
        self, *, session_id: UUID | None = None, page: int = 1, page_size: int = 50
    ) -> list[AuditEvent]:
        """Return audit events, optionally filtered by session."""
        events = self._audit_log
        if session_id is not None:
            events = [e for e in events if e.session_id == session_id]
        start = (page - 1) * page_size
        return events[start:start + page_size]

    def _audit(
        self,
        session_id: UUID,
        action: AutomationAction,
        result: AuditResult,
        details: str = "",
    ) -> None:
        """Record an audit event."""
        event = AuditEvent(
            id=uuid4(),
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            action=action,
            environment=AutomationEnvironment.SANDBOX,
            result=result,
            details=details,
        )
        self._audit_log.append(event)

    def clear(self) -> None:
        """Clear all data (used by tests)."""
        for browser in self._browser_sessions.values():
            browser.stop()
        self._sessions.clear()
        self._approvals.clear()
        self._audit_log.clear()
        self._browser_sessions.clear()


automation_engine = AutomationEngine()
