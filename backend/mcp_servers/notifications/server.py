"""Notifications MCP server.

Closes a real gap: docs/architecture.md has listed a "Notification System —
Alerts and status updates" as a planned-but-never-built layer since this
project's earliest architecture doc, and nothing in this codebase pages a
human when a fulfillment workflow needs review. Every order that stops at
WAITING_APPROVAL (the existing human-approval gate — see
app.services.fulfillment.workflow) or FAILED (e.g. the price safety-gate,
_step_check_price_guard) currently just sits there until someone happens to
check the dashboard; WAITING_APPROVAL even auto-expires after
APPROVAL_EXPIRY_SECONDS (1 hour) if nobody acts.

This server does NOT modify the fulfillment workflow engine itself — it
only reads real state from it (fulfillment_engine.list_workflows/
get_workflow) and calls out through the existing notification-provider
abstraction (app.services.providers.notifications_base, selected via
NOTIFICATION_PROVIDER — see app/core/config.py). No workflow state is ever
changed by any tool here; this is strictly read-and-alert, never a second
approval mechanism and never capable of approving/rejecting anything
itself.

KNOWN LIMITATION — read before relying on list_pending_reviews /
notify_workflow_needs_review across the orchestrator: fulfillment_engine's
workflow state (services/fulfillment/workflow.py) is held purely in an
in-memory dict, per Python process — it is NOT persisted to the
`fulfillment_workflows` table that exists in app/models.py (that table is
defined but never read or written anywhere in this codebase; it predates
and is unrelated to this server). When mcp_servers/orchestrator spawns
this server as its own subprocess (see orchestrator/mcp_servers.json),
it gets its own separate fulfillment_engine instance — it CANNOT see
workflows created via the amazon server's subprocess, or via the main
FastAPI app, since those are different processes entirely. This is a
pre-existing architectural characteristic of the whole fulfillment engine,
not something introduced or fixable within this server's scope. `notify()`
is unaffected (it doesn't depend on shared state) and is fully usable
today; the other two tools are only meaningful when this server runs
in-process with whatever created the workflow (e.g. called directly, not
through a separately-spawned subprocess) until the fulfillment engine
becomes DB-backed.
"""

import logging

from mcp.server.mcpserver import MCPServer

from app.schemas.fulfillment import FulfillmentStatus
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.providers.notifications_base import NotificationProviderError
from app.services.providers.registry import provider_registry

logger = logging.getLogger(__name__)

mcp = MCPServer("notifications")

# Workflow states a human should be told about — everything else (RUNNING,
# COMPLETED, CANCELLED, ...) needs no alert: COMPLETED/CANCELLED are
# resolved states, RUNNING is normal in-flight processing.
_REVIEW_STATUSES = (FulfillmentStatus.WAITING_APPROVAL, FulfillmentStatus.FAILED)


def _notification_error_result(e: NotificationProviderError) -> dict:
    provider = provider_registry.get_notification_provider()
    return {
        "sent": False,
        "configured": provider.is_configured,
        "provider": provider.provider_name,
        "error": e.message,
    }


@mcp.tool()
def notify(title: str, message: str, severity: str = "info") -> dict:
    """Send a notification through the active provider (see
    app.services.providers.registry — NOTIFICATION_PROVIDER selects
    slack/log). severity is one of "info", "warning", "critical".
    """
    provider = provider_registry.get_notification_provider()
    try:
        result = provider.send(title, message, severity)
    except NotificationProviderError as e:
        return _notification_error_result(e)
    return result


@mcp.tool()
def list_pending_reviews() -> dict:
    """List every fulfillment workflow currently sitting in
    WAITING_APPROVAL or FAILED — read-only, changes nothing. Use this to
    find what to notify about with notify_workflow_needs_review.
    """
    pending = [
        {
            "workflow_id": str(wf.id),
            "order_id": str(wf.order_id),
            "status": wf.status.value,
            "order_source": wf.order_source,
            "error_message": wf.error_message,
            "approval_expires_at": (
                wf.approval_expires_at.isoformat() if wf.approval_expires_at else None
            ),
        }
        for wf in fulfillment_engine.list_workflows()
        if wf.status in _REVIEW_STATUSES
    ]
    return {"count": len(pending), "workflows": pending}


@mcp.tool()
def notify_workflow_needs_review(workflow_id: str) -> dict:
    """Send a notification about one specific workflow, built from its
    REAL current state (never from caller-supplied text) — refuses if the
    workflow isn't actually in a state that needs review, so this can't be
    used to send an arbitrary message dressed up as a workflow alert.
    """
    from uuid import UUID

    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        return {"sent": False, "reason": f"Invalid workflow_id: {workflow_id!r}"}

    try:
        wf = fulfillment_engine.get_workflow(wf_uuid)
    except Exception as e:
        return {"sent": False, "reason": str(e)}

    if wf.status not in _REVIEW_STATUSES:
        return {
            "sent": False,
            "reason": f"Workflow {workflow_id} is in status '{wf.status.value}', not one that needs review.",
        }

    if wf.status == FulfillmentStatus.WAITING_APPROVAL:
        title = "Fulfillment order awaiting approval"
        message = (
            f"Order {wf.order_id} (workflow {wf.id}) is waiting for human approval "
            f"before supplier submission."
        )
        if wf.approval_expires_at:
            message += f" Approval expires at {wf.approval_expires_at.isoformat()}."
        severity = "warning"
    else:  # FAILED
        title = "Fulfillment order failed — needs review"
        message = f"Order {wf.order_id} (workflow {wf.id}) failed: {wf.error_message or 'no error message recorded'}"
        severity = "critical"

    provider = provider_registry.get_notification_provider()
    try:
        result = provider.send(title, message, severity)
    except NotificationProviderError as e:
        return _notification_error_result(e)
    return {**result, "workflow_id": workflow_id, "order_id": str(wf.order_id)}


if __name__ == "__main__":
    mcp.run()
