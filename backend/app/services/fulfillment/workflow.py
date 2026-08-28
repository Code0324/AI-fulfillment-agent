"""Fulfillment workflow orchestrator with safety hardening.

Connects order validation, address processing, inventory reservation,
and supplier sandbox into one end-to-end fulfillment workflow.

Safety features:
- Idempotency: prevents duplicate fulfillment for same order
- State machine: explicit transition validation
- Approval expiration: timestamp-based expiry
- Retry safety: prevents duplicate reservations/submissions
- Concurrency protection: per-order locking
- Audit logging: structured reliability events

All data is synthetic — no real Amazon, supplier, or customer data is used.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.errors import NotFoundError, ValidationError
from app.core.security import redact_pii
from app.schemas.address import AddressProcessingStatus
from app.schemas.automation import (
    AutomationAction,
    AutomationEnvironment,
)
from app.schemas.fulfillment import (
    APPROVAL_EXPIRY_SECONDS,
    FulfillmentAuditEvent,
    FulfillmentConfirmation,
    FulfillmentStatus,
    FulfillmentStep,
    FulfillmentStepStatus,
    FulfillmentWorkflow,
    SupplierOrderPayload,
    is_valid_transition,
)
from app.services.address.service import address_processing_service
from app.services.automation.engine import automation_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Workflow step definitions
# ---------------------------------------------------------------------------

WORKFLOW_STEPS = [
    {"name": "load_order", "description": "Load and validate order"},
    {"name": "validate_address", "description": "Parse and validate shipping address"},
    {"name": "check_inventory", "description": "Check inventory availability"},
    {"name": "reserve_inventory", "description": "Reserve inventory for order"},
    {"name": "prepare_supplier_order", "description": "Prepare supplier order payload"},
    {"name": "open_supplier_sandbox", "description": "Open supplier sandbox page"},
    {"name": "fill_product_info", "description": "Fill product information"},
    {"name": "fill_shipping_address", "description": "Fill shipping address"},
    {"name": "select_shipping_method", "description": "Select shipping method"},
    {"name": "verify_order", "description": "Verify order before submission"},
    {"name": "request_approval", "description": "Request human approval for submission"},
    {"name": "submit_supplier_order", "description": "Submit order to mock supplier"},
    {"name": "generate_confirmation", "description": "Generate fulfillment confirmation"},
]

SHIPPING_METHODS = ["standard", "express", "priority"]


class FulfillmentWorkflowEngine:
    """Orchestrates the end-to-end fulfillment workflow with safety hardening."""

    def __init__(self) -> None:
        self._workflows: dict[UUID, FulfillmentWorkflow] = {}
        self._order_workflows: dict[UUID, UUID] = {}  # order_id -> workflow_id
        self._confirmation_ids: set[str] = set()  # Track confirmation IDs
        self._order_locks: dict[UUID, threading.Lock] = {}  # Per-order locks
        self._locks_lock = threading.Lock()  # Guards creation of per-order locks
        self._audit_log: list[FulfillmentAuditEvent] = []

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def start_workflow(
        self,
        order_id: UUID,
        shipping_method: str = "standard",
    ) -> FulfillmentWorkflow:
        """Start a new fulfillment workflow for an order.

        Idempotency: If an active workflow exists for this order,
        returns the existing workflow instead of creating a duplicate.
        """
        # Get or create per-order lock
        lock = self._get_order_lock(order_id)
        with lock:
            # Idempotency check
            existing_id = self._order_workflows.get(order_id)
            if existing_id is not None:
                existing = self._workflows.get(existing_id)
                if existing is not None and existing.status not in (
                    FulfillmentStatus.COMPLETED,
                    FulfillmentStatus.CANCELLED,
                    FulfillmentStatus.FAILED,
                    FulfillmentStatus.EXPIRED,
                ):
                    self._audit(
                        existing.id, order_id,
                        "DUPLICATE_REQUEST_BLOCKED",
                        f"Active workflow {existing.id} exists for order",
                    )
                    return existing
                # If previous workflow was terminal, allow new one

            # Validate order exists
            order = order_service.get(order_id)

            # Validate shipping method
            if shipping_method not in SHIPPING_METHODS:
                raise ValidationError(
                    f"Invalid shipping method '{shipping_method}'. "
                    f"Allowed: {SHIPPING_METHODS}"
                )

            now = datetime.now(timezone.utc)
            steps = [
                FulfillmentStep(
                    name=s["name"],
                    description=s["description"],
                    status=FulfillmentStepStatus.PENDING,
                )
                for s in WORKFLOW_STEPS
            ]

            workflow = FulfillmentWorkflow(
                id=uuid4(),
                order_id=order_id,
                status=FulfillmentStatus.PENDING,
                steps=steps,
                current_step=0,
                created_at=now,
                updated_at=now,
            )
            self._workflows[workflow.id] = workflow
            self._order_workflows[order_id] = workflow.id

            self._audit(
                workflow.id, order_id,
                "FULFILLMENT_STARTED",
                f"Workflow started with shipping method: {shipping_method}",
            )

            logger.info(
                "Fulfillment workflow started: %s for order %s",
                workflow.id,
                order_id,
            )

            # Execute the workflow steps
            return self._execute_workflow(workflow, shipping_method)

    def get_workflow(self, workflow_id: UUID) -> FulfillmentWorkflow:
        """Return one workflow by ID."""
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise NotFoundError("Fulfillment workflow not found")

        # Check for approval expiration
        if workflow.status == FulfillmentStatus.WAITING_APPROVAL:
            if workflow.is_approval_expired:
                return self._expire_workflow(workflow)

        return workflow

    def list_workflows(
        self, *, page: int = 1, page_size: int = 10
    ) -> list[FulfillmentWorkflow]:
        """Return all workflows."""
        return list(self._workflows.values())

    def approve_workflow(self, workflow_id: UUID) -> FulfillmentWorkflow:
        """Approve a workflow waiting for approval and complete it."""
        workflow = self.get_workflow(workflow_id)

        lock = self._get_order_lock(workflow.order_id)
        with lock:
            if workflow.status != FulfillmentStatus.WAITING_APPROVAL:
                raise ValidationError(
                    f"Workflow is not waiting for approval (status: {workflow.status.value})"
                )

            # Check expiration
            if workflow.is_approval_expired:
                return self._expire_workflow(workflow)

            # Transition to APPROVED
            self._transition(workflow, FulfillmentStatus.APPROVED)

            # Mark approval step as completed
            for step in workflow.steps:
                if step.status == FulfillmentStepStatus.WAITING_APPROVAL:
                    step.status = FulfillmentStepStatus.COMPLETED
                    step.completed_at = datetime.now(timezone.utc)
                    step.result = "Approved by human"
                    break

            self._audit(
                workflow.id, workflow.order_id,
                "APPROVAL_APPROVED",
                "Human approved supplier submission",
            )

            # Continue with remaining steps
            return self._continue_workflow(workflow)

    def reject_workflow(self, workflow_id: UUID) -> FulfillmentWorkflow:
        """Reject a workflow waiting for approval."""
        workflow = self.get_workflow(workflow_id)

        lock = self._get_order_lock(workflow.order_id)
        with lock:
            if workflow.status != FulfillmentStatus.WAITING_APPROVAL:
                raise ValidationError(
                    f"Workflow is not waiting for approval (status: {workflow.status.value})"
                )

            # Transition to CANCELLED
            self._transition(workflow, FulfillmentStatus.CANCELLED)

            # Mark approval step as failed
            for step in workflow.steps:
                if step.status == FulfillmentStepStatus.WAITING_APPROVAL:
                    step.status = FulfillmentStepStatus.FAILED
                    step.completed_at = datetime.now(timezone.utc)
                    step.error = "Rejected by human"
                    break

            self._audit(
                workflow.id, workflow.order_id,
                "APPROVAL_REJECTED",
                "Human rejected supplier submission",
            )

            # Release inventory if it was reserved
            self._release_inventory_if_reserved(workflow)

            logger.info("Fulfillment workflow rejected: %s", workflow.id)
            return workflow

    def cancel_workflow(self, workflow_id: UUID) -> FulfillmentWorkflow:
        """Cancel a workflow if its state allows cancellation."""
        workflow = self.get_workflow(workflow_id)

        lock = self._get_order_lock(workflow.order_id)
        with lock:
            if not is_valid_transition(workflow.status, FulfillmentStatus.CANCELLED):
                raise ValidationError(
                    f"Cannot cancel workflow in status '{workflow.status.value}'"
                )

            # Transition to CANCELLED
            self._transition(workflow, FulfillmentStatus.CANCELLED)

            self._audit(
                workflow.id, workflow.order_id,
                "FULFILLMENT_CANCELLED",
                f"Workflow cancelled from status: {workflow.status.value}",
            )

            # Release inventory if it was reserved
            self._release_inventory_if_reserved(workflow)

            logger.info("Fulfillment workflow cancelled: %s", workflow.id)
            return workflow

    def retry_workflow(self, workflow_id: UUID) -> FulfillmentWorkflow:
        """Retry a failed/expired/cancelled workflow safely.

        Retry safety:
        - Does not duplicate inventory reservation
        - Does not duplicate supplier submission
        - Still requires approval for high-risk action
        """
        workflow = self.get_workflow(workflow_id)

        lock = self._get_order_lock(workflow.order_id)
        with lock:
            if not workflow.can_retry:
                raise ValidationError(
                    f"Cannot retry workflow in status '{workflow.status.value}'"
                )

            self._audit(
                workflow.id, workflow.order_id,
                "RETRY_STARTED",
                f"Retrying from status: {workflow.status.value} (attempt {workflow.retry_count + 1})",
            )

            # Reset workflow for retry
            workflow.retry_count += 1
            workflow.error_message = None
            workflow.approval_request_id = None
            workflow.approval_requested_at = None
            workflow.approval_expires_at = None
            workflow.supplier_payload = None
            workflow.confirmation = None
            workflow.current_step = 0

            # Reset ALL steps — retry starts fresh
            for step in workflow.steps:
                step.status = FulfillmentStepStatus.PENDING
                step.error = None
                step.result = None
                step.started_at = None
                step.completed_at = None

            # Transition to RUNNING
            self._transition(workflow, FulfillmentStatus.RUNNING)

            # Execute from where we left off
            order = order_service.get(workflow.order_id)
            shipping_method = (
                workflow.supplier_payload.shipping_method
                if workflow.supplier_payload
                else "standard"
            )

            return self._execute_workflow_from_step(workflow, shipping_method)

    # ------------------------------------------------------------------
    # Internal workflow execution
    # ------------------------------------------------------------------

    def _execute_workflow(
        self, workflow: FulfillmentWorkflow, shipping_method: str
    ) -> FulfillmentWorkflow:
        """Execute workflow steps sequentially from the beginning."""
        self._transition(workflow, FulfillmentStatus.RUNNING)
        return self._execute_workflow_from_step(workflow, shipping_method)

    def _execute_workflow_from_step(
        self, workflow: FulfillmentWorkflow, shipping_method: str
    ) -> FulfillmentWorkflow:
        """Execute workflow steps from current step."""
        order = order_service.get(workflow.order_id)

        try:
            # Step 0: Load Order (always re-run on retry)
            if workflow.steps[0].status != FulfillmentStepStatus.COMPLETED:
                self._run_step(workflow, 0, lambda: self._step_load_order(order))

            # Step 1: Validate Address
            if workflow.steps[1].status != FulfillmentStepStatus.COMPLETED:
                address_result = self._run_step(
                    workflow, 1, lambda: self._step_validate_address(order)
                )
                if address_result and address_result.get("status") in (
                    AddressProcessingStatus.FAILED.value,
                    AddressProcessingStatus.NEEDS_REVIEW.value,
                ):
                    self._fail_workflow(
                        workflow,
                        f"Address validation failed: {address_result.get('reason', 'needs review')}",
                    )
                    return workflow
            else:
                address_result = _parse_step_result(workflow.steps[1].result)

            # Step 2: Check Inventory
            if workflow.steps[2].status != FulfillmentStepStatus.COMPLETED:
                self._run_step(
                    workflow, 2, lambda: self._step_check_inventory(order)
                )

            # Step 3: Reserve Inventory (idempotent — skips if already reserved)
            if workflow.steps[3].status != FulfillmentStepStatus.COMPLETED:
                self._run_step(
                    workflow, 3, lambda: self._step_reserve_inventory(order)
                )

            # Step 4: Prepare Supplier Order
            if workflow.steps[4].status != FulfillmentStepStatus.COMPLETED:
                supplier_payload = self._run_step(
                    workflow, 4, lambda: self._step_prepare_supplier_order(
                        order, address_result, shipping_method
                    )
                )
                workflow.supplier_payload = supplier_payload
            else:
                supplier_payload = workflow.supplier_payload

            # Step 5: Open Supplier Sandbox
            if workflow.steps[5].status != FulfillmentStepStatus.COMPLETED:
                session = self._run_step(
                    workflow, 5, lambda: self._step_open_sandbox()
                )
            else:
                session = _parse_step_result(workflow.steps[5].result)

            # Step 6: Fill Product Info
            if workflow.steps[6].status != FulfillmentStepStatus.COMPLETED:
                self._run_step(
                    workflow, 6, lambda: self._step_fill_product(session, supplier_payload)
                )

            # Step 7: Fill Shipping Address
            if workflow.steps[7].status != FulfillmentStepStatus.COMPLETED:
                self._run_step(
                    workflow, 7, lambda: self._step_fill_address(session, address_result)
                )

            # Step 8: Select Shipping Method
            if workflow.steps[8].status != FulfillmentStepStatus.COMPLETED:
                self._run_step(
                    workflow, 8, lambda: self._step_select_shipping(
                        session, shipping_method
                    )
                )

            # Step 9: Verify Order
            if workflow.steps[9].status != FulfillmentStepStatus.COMPLETED:
                self._run_step(
                    workflow, 9, lambda: self._step_verify_order(supplier_payload)
                )

            # Step 10: Request Approval (HIGH-RISK)
            if workflow.steps[10].status != FulfillmentStepStatus.COMPLETED:
                workflow = self._step_request_approval(workflow, session)
                if workflow.status == FulfillmentStatus.WAITING_APPROVAL:
                    return workflow

        except Exception as e:
            self._fail_workflow(workflow, str(e))

        return workflow

    def _continue_workflow(self, workflow: FulfillmentWorkflow) -> FulfillmentWorkflow:
        """Continue workflow after approval."""
        self._transition(workflow, FulfillmentStatus.RUNNING)

        try:
            # Step 11: Submit Supplier Order
            if workflow.steps[11].status != FulfillmentStepStatus.COMPLETED:
                # Submission safety: check for duplicate
                if workflow.confirmation is not None:
                    self._audit(
                        workflow.id, workflow.order_id,
                        "SUPPLIER_SUBMISSION_BLOCKED",
                        f"Already submitted with confirmation: {workflow.confirmation.confirmation_id}",
                    )
                    return workflow

                self._run_step(
                    workflow, 11, lambda: self._step_submit_order()
                )

            # Step 12: Generate Confirmation
            if workflow.steps[12].status != FulfillmentStepStatus.COMPLETED:
                if workflow.confirmation is not None:
                    # Confirmation already exists
                    return workflow

                confirmation = self._run_step(
                    workflow, 12, lambda: self._step_generate_confirmation()
                )
                workflow.confirmation = confirmation

                # Track confirmation ID
                self._confirmation_ids.add(confirmation.confirmation_id)

            # Complete workflow
            self._transition(workflow, FulfillmentStatus.COMPLETED)

            # Update order status to processing
            from app.schemas.order import OrderStatus
            order_service.update_status(workflow.order_id, OrderStatus.PROCESSING)

            self._audit(
                workflow.id, workflow.order_id,
                "FULFILLMENT_COMPLETED",
                f"Confirmation: {workflow.confirmation.confirmation_id if workflow.confirmation else 'N/A'}",
            )

            logger.info("Fulfillment workflow completed: %s", workflow.id)

        except Exception as e:
            self._fail_workflow(workflow, str(e))

        return workflow

    def _run_step(
        self,
        workflow: FulfillmentWorkflow,
        step_index: int,
        step_fn,
    ) -> Any:
        """Run a single workflow step."""
        if step_index >= len(workflow.steps):
            raise ValidationError(f"Step index {step_index} out of range")

        step = workflow.steps[step_index]
        now = datetime.now(timezone.utc)
        step.status = FulfillmentStepStatus.RUNNING
        step.started_at = now
        workflow.current_step = step_index
        workflow.updated_at = now

        try:
            result = step_fn()
            step.status = FulfillmentStepStatus.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            step.result = str(result) if result else "OK"
            return result
        except Exception as e:
            step.status = FulfillmentStepStatus.FAILED
            step.completed_at = datetime.now(timezone.utc)
            step.error = str(e)

            self._audit(
                workflow.id, workflow.order_id,
                "STEP_FAILED",
                f"Step '{step.name}' failed: {str(e)[:200]}",
            )
            raise

    def _fail_workflow(self, workflow: FulfillmentWorkflow, error: str) -> None:
        """Mark workflow as failed."""
        now = datetime.now(timezone.utc)
        workflow.status = FulfillmentStatus.FAILED
        workflow.error_message = error
        workflow.updated_at = now

        self._audit(
            workflow.id, workflow.order_id,
            "FULFILLMENT_FAILED",
            error[:200],
        )

        # Release inventory if it was reserved
        self._release_inventory_if_reserved(workflow)

        logger.error("Fulfillment workflow failed: %s — %s", workflow.id, error)

    def _expire_workflow(self, workflow: FulfillmentWorkflow) -> FulfillmentWorkflow:
        """Expire a workflow whose approval has timed out."""
        lock = self._get_order_lock(workflow.order_id)
        with lock:
            if workflow.status != FulfillmentStatus.WAITING_APPROVAL:
                return workflow

            self._transition(workflow, FulfillmentStatus.EXPIRED)

            for step in workflow.steps:
                if step.status == FulfillmentStepStatus.WAITING_APPROVAL:
                    step.status = FulfillmentStepStatus.FAILED
                    step.completed_at = datetime.now(timezone.utc)
                    step.error = "Approval expired"
                    break

            self._audit(
                workflow.id, workflow.order_id,
                "APPROVAL_EXPIRED",
                f"Approval expired at {workflow.approval_expires_at}",
            )

            # Release inventory
            self._release_inventory_if_reserved(workflow)

            logger.info("Fulfillment workflow expired: %s", workflow.id)
            return workflow

    def _transition(
        self, workflow: FulfillmentWorkflow, target: FulfillmentStatus
    ) -> None:
        """Validate and perform a state transition."""
        if not is_valid_transition(workflow.status, target):
            raise ValidationError(
                f"Invalid transition: {workflow.status.value} → {target.value}"
            )
        workflow.status = target
        workflow.updated_at = datetime.now(timezone.utc)

    def _release_inventory_if_reserved(self, workflow: FulfillmentWorkflow) -> None:
        """Release inventory if it was reserved during this workflow."""
        order = order_service.get(workflow.order_id)
        if order.inventory_reserved and order.sku:
            try:
                inventory_service.release(order.sku, order.quantity)
                order_service.clear_inventory_reservation(order.id)
                self._audit(
                    workflow.id, workflow.order_id,
                    "INVENTORY_RELEASED",
                    f"Released {order.quantity} units of SKU {order.sku}",
                )
                logger.info("Released inventory for order %s", workflow.order_id)
            except Exception as e:
                logger.error("Failed to release inventory: %s", e)

    def _get_order_lock(self, order_id: UUID) -> threading.Lock:
        """Get or create a lock for an order.

        Guarded by _locks_lock: without it, two concurrent requests for the
        same never-before-seen order could each create a distinct Lock and
        both believe they hold exclusive access.
        """
        with self._locks_lock:
            lock = self._order_locks.get(order_id)
            if lock is None:
                lock = threading.Lock()
                self._order_locks[order_id] = lock
            return lock

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def _audit(
        self,
        workflow_id: UUID,
        order_id: UUID,
        event_type: str,
        details: str = "",
        error_message: str | None = None,
    ) -> None:
        """Record a structured audit event."""
        event = FulfillmentAuditEvent(
            id=uuid4(),
            workflow_id=workflow_id,
            order_id=order_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            details=details[:500],
            error_message=error_message,
        )
        self._audit_log.append(event)

    def get_audit_log(
        self,
        workflow_id: UUID | None = None,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[FulfillmentAuditEvent]:
        """Return audit events, optionally filtered by workflow."""
        events = self._audit_log
        if workflow_id is not None:
            events = [e for e in events if e.workflow_id == workflow_id]
        start = (page - 1) * page_size
        return events[start : start + page_size]

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _step_load_order(self, order) -> dict:
        """Step: Load and validate order."""
        return {
            "order_id": str(order.id),
            "customer": order.customer_name,
            "product": order.product_name,
            "sku": order.sku,
            "quantity": order.quantity,
        }

    def _step_validate_address(self, order) -> dict:
        """Step: Parse and validate shipping address."""
        result = address_processing_service.parse(order.shipping_address)
        return {
            "status": result.status.value,
            "confidence": result.confidence,
            "reason": result.review_reason,
            "first_name": result.first_name,
            "last_name": result.last_name,
            "address_line_1": result.address_line_1,
            "address_line_2": result.address_line_2,
            "city": result.city,
            "state": result.state,
            "postal_code": result.postal_code,
            "country": result.country,
        }

    def _step_check_inventory(self, order) -> dict:
        """Step: Check inventory availability."""
        if not order.sku:
            return {"available": False, "reason": "No SKU on order"}
        item = inventory_service.find_by_sku(order.sku)
        if item is None:
            return {"available": False, "reason": f"No inventory for SKU {order.sku}"}
        return {
            "available": item.available_quantity >= order.quantity,
            "sku": order.sku,
            "requested": order.quantity,
            "available": item.available_quantity,
        }

    def _step_reserve_inventory(self, order) -> dict:
        """Step: Reserve inventory if not already reserved (idempotent)."""
        # Always get fresh order state to handle retries correctly
        fresh_order = order_service.get(order.id)
        if fresh_order.inventory_reserved:
            self._audit(
                fresh_order.id, fresh_order.id,
                "INVENTORY_RESERVED",
                "Already reserved — skipping",
            )
            return {"reserved": True, "reason": "Already reserved"}
        if not fresh_order.sku:
            return {"reserved": False, "reason": "No SKU"}
        # order_service.reserve_inventory handles both inventory reservation
        # and order update — do NOT call inventory_service.reserve separately
        order_service.reserve_inventory(fresh_order.id)

        self._audit(
            fresh_order.id, fresh_order.id,
            "INVENTORY_RESERVED",
            f"Reserved {fresh_order.quantity} units of SKU {fresh_order.sku}",
        )
        return {"reserved": True, "sku": fresh_order.sku, "quantity": fresh_order.quantity}

    def _step_prepare_supplier_order(
        self, order, address_result: dict, shipping_method: str
    ) -> SupplierOrderPayload:
        """Step: Prepare supplier order payload."""
        return SupplierOrderPayload(
            sku=order.sku or "UNKNOWN",
            product_name=order.product_name,
            quantity=order.quantity,
            first_name=address_result.get("first_name", "Test"),
            last_name=address_result.get("last_name", "Customer"),
            address_line_1=address_result.get("address_line_1", "123 Test St"),
            address_line_2=address_result.get("address_line_2", ""),
            city=address_result.get("city", "Testville"),
            state=address_result.get("state", "CA"),
            postal_code=address_result.get("postal_code", "90210"),
            country=address_result.get("country", "US"),
            phone=address_result.get("phone", ""),
            shipping_method=shipping_method,
        )

    def _step_open_sandbox(self) -> dict:
        """Step: Open supplier sandbox."""
        session = automation_engine.create_session(AutomationEnvironment.SANDBOX)
        return {"session_id": str(session.id)}

    def _step_fill_product(self, session_info: dict, payload: SupplierOrderPayload) -> dict:
        """Step: Fill product information."""
        session_id = UUID(session_info["session_id"])
        browser = automation_engine._browser_sessions.get(session_id)
        if browser is None:
            raise ValidationError("No browser session")

        filled = []
        for selector, value in [
            ("#sku", payload.sku),
            ("#product_name", payload.product_name),
            ("#quantity", str(payload.quantity)),
        ]:
            result = browser.fill_field(selector, value)
            if result.success:
                filled.append(selector)

        return {"filled_fields": filled}

    def _step_fill_address(self, session_info: dict, address_result: dict) -> dict:
        """Step: Fill shipping address in supplier form."""
        session_id = UUID(session_info["session_id"])
        browser = automation_engine._browser_sessions.get(session_id)
        if browser is None:
            raise ValidationError("No browser session")

        field_map = {
            "#first_name": address_result.get("first_name", ""),
            "#last_name": address_result.get("last_name", ""),
            "#address1": address_result.get("address_line_1", ""),
            "#address2": address_result.get("address_line_2", ""),
            "#city": address_result.get("city", ""),
            "#state": address_result.get("state", ""),
            "#zip": address_result.get("postal_code", ""),
            "#country": address_result.get("country", "US"),
            "#phone": address_result.get("phone", ""),
        }

        filled = []
        for selector, value in field_map.items():
            if value:
                result = browser.fill_field(selector, value)
                if result.success:
                    filled.append(selector)

        return {"filled_fields": filled}

    def _step_select_shipping(self, session_info: dict, method: str) -> dict:
        """Step: Select shipping method."""
        session_id = UUID(session_info["session_id"])
        browser = automation_engine._browser_sessions.get(session_id)
        if browser is None:
            raise ValidationError("No browser session")

        result = browser.select_option("#shipping_method", method)
        return {"selected": method, "success": result.success}

    def _step_verify_order(self, payload: SupplierOrderPayload) -> dict:
        """Step: Verify order before submission."""
        issues = []
        if not payload.sku or payload.sku == "UNKNOWN":
            issues.append("Missing SKU")
        if payload.quantity < 1:
            issues.append("Invalid quantity")
        if not payload.first_name:
            issues.append("Missing first name")
        if not payload.address_line_1:
            issues.append("Missing address")
        if not payload.city:
            issues.append("Missing city")

        if issues:
            raise ValidationError(f"Verification failed: {', '.join(issues)}")

        return {"verified": True, "sku": payload.sku, "quantity": payload.quantity}

    def _step_request_approval(
        self, workflow: FulfillmentWorkflow, session_info: dict
    ) -> FulfillmentWorkflow:
        """Step: Request human approval for high-risk submission."""
        session_id = UUID(session_info["session_id"])

        # Request approval through automation engine
        approval = automation_engine.request_approval(
            session_id,
            AutomationAction.SUBMIT,
            f"Submit supplier order for SKU {workflow.supplier_payload.sku if workflow.supplier_payload else 'unknown'}",
        )

        workflow.approval_request_id = approval.id
        workflow.approval_requested_at = datetime.now(timezone.utc)
        workflow.approval_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=APPROVAL_EXPIRY_SECONDS
        )

        # Transition to WAITING_APPROVAL
        self._transition(workflow, FulfillmentStatus.WAITING_APPROVAL)

        # Mark the approval step as waiting
        for step in workflow.steps:
            if step.name == "request_approval":
                step.status = FulfillmentStepStatus.WAITING_APPROVAL
                step.result = f"Approval request {approval.id}"
                break

        self._audit(
            workflow.id, workflow.order_id,
            "APPROVAL_REQUESTED",
            f"Approval request {approval.id}, expires at {workflow.approval_expires_at}",
        )

        return workflow

    def _step_submit_order(self) -> dict:
        """Step: Submit order to mock supplier."""
        # In sandbox, this just simulates submission
        return {"submitted": True, "supplier": "MOCK SUPPLIER"}

    def _step_generate_confirmation(self) -> FulfillmentConfirmation:
        """Step: Generate fulfillment confirmation."""
        # Generate unique confirmation ID
        confirmation_id = f"SUP-{uuid4().hex[:8].upper()}"
        while confirmation_id in self._confirmation_ids:
            confirmation_id = f"SUP-{uuid4().hex[:8].upper()}"

        return FulfillmentConfirmation(
            confirmation_id=confirmation_id,
            supplier="MOCK SUPPLIER",
            status="submitted",
            submitted_at=datetime.now(timezone.utc),
            estimated_delivery="5-7 business days",
        )

    def clear(self) -> None:
        """Clear all workflows (used by tests)."""
        self._workflows.clear()
        self._order_workflows.clear()
        self._confirmation_ids.clear()
        self._order_locks.clear()
        self._audit_log.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_step_result(result_str: str | None) -> dict:
    """Parse a step result string back to dict (best-effort)."""
    if not result_str:
        return {}
    # Simple parsing for common patterns
    try:
        import ast
        return ast.literal_eval(result_str)
    except (ValueError, SyntaxError):
        return {"raw": result_str}


fulfillment_engine = FulfillmentWorkflowEngine()
