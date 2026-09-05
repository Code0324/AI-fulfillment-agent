"""Notification provider tests.

No real Slack calls — the webhook provider's "not configured" path is
exercised live; its real-send path is not (no webhook URL available in
this sandbox — see slack/webhook.py's module docstring).
"""

import pytest

from app.core.config import settings
from app.services.providers.mock.mock_notifications import LogNotificationProvider
from app.services.providers.notifications_base import (
    NotificationProviderNotConfiguredError,
    NotificationProviderRequestError,
)
from app.services.providers.registry import ProviderRegistry, create_default_registry
from app.services.providers.slack.webhook import SlackWebhookNotificationProvider


class TestLogNotificationProvider:
    def test_always_configured(self):
        assert LogNotificationProvider().is_configured is True

    def test_send_writes_a_real_log_line_and_reports_it_truthfully(self, caplog):
        import logging

        provider = LogNotificationProvider()
        with caplog.at_level(logging.INFO, logger="app.notifications"):
            result = provider.send("Test Title", "Test message body", "info")

        assert result["sent"] is True
        assert result["channel"] == "log"
        assert any("Test Title" in r.message and "Test message body" in r.message for r in caplog.records)

    def test_severity_maps_to_appropriate_log_level(self, caplog):
        import logging

        provider = LogNotificationProvider()
        with caplog.at_level(logging.WARNING, logger="app.notifications"):
            provider.send("W", "warn message", "warning")
        assert any(r.levelname == "WARNING" for r in caplog.records)


class TestSlackWebhookNotificationProviderNotConfigured:
    def test_not_configured_without_webhook_url(self):
        assert SlackWebhookNotificationProvider(webhook_url="").is_configured is False

    def test_send_raises_when_not_configured(self):
        provider = SlackWebhookNotificationProvider(webhook_url="")
        with pytest.raises(NotificationProviderNotConfiguredError):
            provider.send("t", "m")

    def test_never_constructs_an_http_client_when_not_configured(self, monkeypatch):
        import httpx

        def _boom(*a, **k):
            raise AssertionError("must not construct an HTTP client when unconfigured")

        monkeypatch.setattr(httpx, "Client", _boom)
        with pytest.raises(NotificationProviderNotConfiguredError):
            SlackWebhookNotificationProvider(webhook_url="").send("t", "m")

    def test_configured_with_a_webhook_url(self):
        assert SlackWebhookNotificationProvider(webhook_url="https://hooks.slack.test/x").is_configured is True


class TestSlackWebhookResponseHandling:
    """Response-parsing logic only, against a stubbed httpx client — never
    a real POST to Slack (no webhook URL available in this sandbox)."""

    def test_non_ok_body_is_treated_as_failure(self, monkeypatch):
        import httpx

        class _FakeResponse:
            status_code = 200
            text = "invalid_payload"

        class _FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, *a, **k):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "Client", lambda: _FakeClient())
        provider = SlackWebhookNotificationProvider(webhook_url="https://hooks.slack.test/x")
        with pytest.raises(NotificationProviderRequestError):
            provider.send("t", "m")

    def test_ok_body_reports_success(self, monkeypatch):
        import httpx

        class _FakeResponse:
            status_code = 200
            text = "ok"

        class _FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, *a, **k):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "Client", lambda: _FakeClient())
        provider = SlackWebhookNotificationProvider(webhook_url="https://hooks.slack.test/x")
        result = provider.send("t", "m")
        assert result["sent"] is True
        assert result["channel"] == "slack"


class TestRegistryNotificationProviderSelection:
    def test_defaults_to_log(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "log")
        registry = create_default_registry()
        assert registry.get_notification_provider().provider_name == "log_notification_provider"

    def test_selects_slack(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "slack")
        registry = create_default_registry()
        assert registry.get_notification_provider().provider_name == "slack_webhook_notification_provider"

    def test_unrecognized_value_falls_back_to_log(self, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "bogus")
        registry = create_default_registry()
        assert registry.get_notification_provider().provider_name == "log_notification_provider"

    def test_get_notification_provider_without_one_set_raises(self):
        registry = ProviderRegistry()
        with pytest.raises(RuntimeError):
            registry.get_notification_provider()
