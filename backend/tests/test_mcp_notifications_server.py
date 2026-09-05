"""Notifications MCP server tests.

No real Slack/network calls (log provider only). fulfillment_engine is a
pure in-memory singleton (see services/fulfillment/workflow.py) — tests
that need pending workflows inject FulfillmentWorkflow objects directly
into it rather than going through the full order_service+DB-backed
start_workflow path, mirroring test_mcp_orchestrator.py's white-box
approach for MultiClientManager.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.schemas.fulfillment import FulfillmentStatus, FulfillmentWorkflow
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.providers.mock.mock_notifications import LogNotificationProvider
from app.services.providers.registry import provider_registry

from mcp_servers.notifications import server as notif_server


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    fulfillment_engine.clear()
    provider_registry.set_notification_provider(LogNotificationProvider())
    yield
    fulfillment_engine.clear()
    provider_registry.set_notification_provider(LogNotificationProvider())


def _inject_workflow(status: FulfillmentStatus, error_message: str | None = None) -> FulfillmentWorkflow:
    """White-box: insert a workflow directly into fulfillment_engine's
    in-memory store, bypassing order_service/DB entirely."""
    now = datetime.now(timezone.utc)
    wf = FulfillmentWorkflow(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        status=status,
        order_source="MANUAL",
        error_message=error_message,
        created_at=now,
        updated_at=now,
    )
    fulfillment_engine._workflows[wf.id] = wf
    return wf


def test_lists_expected_tools():
    tools = asyncio.run(notif_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"notify", "list_pending_reviews", "notify_workflow_needs_review"}


class TestNotify:
    def test_sends_via_active_provider(self):
        result = notif_server.notify("Title", "Message body", "info")
        assert result["sent"] is True
        assert result["channel"] == "log"

    def test_default_severity_is_info(self):
        result = notif_server.notify("Title", "Message body")
        assert result["sent"] is True


class TestListPendingReviews:
    def test_empty_when_no_workflows(self):
        result = notif_server.list_pending_reviews()
        assert result == {"count": 0, "workflows": []}

    def test_finds_waiting_approval_and_failed_only(self):
        waiting = _inject_workflow(FulfillmentStatus.WAITING_APPROVAL)
        failed = _inject_workflow(FulfillmentStatus.FAILED, error_message="price too high")
        _inject_workflow(FulfillmentStatus.COMPLETED)
        _inject_workflow(FulfillmentStatus.RUNNING)

        result = notif_server.list_pending_reviews()

        ids = {w["workflow_id"] for w in result["workflows"]}
        assert result["count"] == 2
        assert ids == {str(waiting.id), str(failed.id)}

    def test_never_mutates_workflow_state(self):
        wf = _inject_workflow(FulfillmentStatus.WAITING_APPROVAL)
        notif_server.list_pending_reviews()
        assert fulfillment_engine._workflows[wf.id].status == FulfillmentStatus.WAITING_APPROVAL


class TestNotifyWorkflowNeedsReview:
    def test_invalid_workflow_id_is_rejected(self):
        result = notif_server.notify_workflow_needs_review("not-a-uuid")
        assert result["sent"] is False

    def test_nonexistent_workflow_is_rejected(self):
        result = notif_server.notify_workflow_needs_review(str(uuid.uuid4()))
        assert result["sent"] is False

    def test_refuses_to_notify_about_a_workflow_not_needing_review(self):
        """A COMPLETED workflow must not be notifiable — this tool can't be
        used to send an arbitrary message dressed up as a workflow alert."""
        wf = _inject_workflow(FulfillmentStatus.COMPLETED)
        result = notif_server.notify_workflow_needs_review(str(wf.id))
        assert result["sent"] is False
        assert "not one that needs review" in result["reason"]

    def test_sends_real_alert_for_waiting_approval(self):
        wf = _inject_workflow(FulfillmentStatus.WAITING_APPROVAL)
        result = notif_server.notify_workflow_needs_review(str(wf.id))
        assert result["sent"] is True
        assert result["workflow_id"] == str(wf.id)

    def test_sends_real_alert_for_failed_including_error_message(self, caplog):
        import logging

        wf = _inject_workflow(FulfillmentStatus.FAILED, error_message="Amazon price $999.99 exceeds maximum")
        with caplog.at_level(logging.ERROR, logger="app.notifications"):
            result = notif_server.notify_workflow_needs_review(str(wf.id))
        assert result["sent"] is True
        assert any("exceeds maximum" in r.message for r in caplog.records)

    def test_does_not_mutate_workflow_state(self):
        wf = _inject_workflow(FulfillmentStatus.WAITING_APPROVAL)
        notif_server.notify_workflow_needs_review(str(wf.id))
        assert fulfillment_engine._workflows[wf.id].status == FulfillmentStatus.WAITING_APPROVAL
