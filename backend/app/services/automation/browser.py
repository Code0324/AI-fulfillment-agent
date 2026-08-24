"""Browser automation abstraction layer.

Provides a clean interface for browser-based workflows.
Supports mock (for testing) and Playwright (for real automation).
"""

import abc
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("app.automation")


@dataclass
class BrowserConfig:
    """Configuration for browser automation."""

    headless: bool = True
    timeout_ms: int = 30000
    screenshot_dir: str = "screenshots"
    environment: str = "sandbox"


@dataclass
class ElementInfo:
    """Information about a detected element."""

    selector: str
    tag: str
    text: str = ""
    value: str = ""
    found: bool = True


@dataclass
class NavigationResult:
    """Result of a page navigation."""

    success: bool
    url: str
    title: str = ""
    error: str | None = None


@dataclass
class FillResult:
    """Result of a form fill operation."""

    success: bool
    field: str
    value: str
    error: str | None = None


@dataclass
class ScreenshotResult:
    """Result of a screenshot capture."""

    success: bool
    path: str | None = None
    error: str | None = None


class BrowserError(Exception):
    """Base browser automation error."""

    def __init__(self, message: str, recoverable: bool = True):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


class CaptchaDetectedError(BrowserError):
    """CAPTCHA detected — automation must stop."""

    def __init__(self):
        super().__init__("CAPTCHA detected — stopping automation", recoverable=False)


class MfaDetectedError(BrowserError):
    """MFA/2FA detected — automation must stop."""

    def __init__(self):
        super().__init__("MFA/2FA detected — stopping automation", recoverable=False)


class AuthenticationRequiredError(BrowserError):
    """Unexpected authentication required — automation must stop."""

    def __init__(self):
        super().__init__("Authentication required — stopping automation", recoverable=False)


class ElementNotFoundError(BrowserError):
    """Expected element not found on page."""

    def __init__(self, selector: str):
        super().__init__(f"Element not found: {selector}", recoverable=True)


class PageChangedError(BrowserError):
    """Page structure changed or unexpected page appeared."""

    def __init__(self, message: str = "Unexpected page structure"):
        super().__init__(message, recoverable=True)


class BrowserSession(abc.ABC):
    """Abstract browser session interface."""

    @abc.abstractmethod
    def start(self) -> None:
        """Start the browser session."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop the browser session and cleanup."""

    @abc.abstractmethod
    def navigate(self, url: str) -> NavigationResult:
        """Navigate to a URL."""

    @abc.abstractmethod
    def find_element(self, selector: str) -> ElementInfo:
        """Find an element by selector."""

    @abc.abstractmethod
    def fill_field(self, selector: str, value: str) -> FillResult:
        """Fill a form field."""

    @abc.abstractmethod
    def select_option(self, selector: str, value: str) -> FillResult:
        """Select an option from a dropdown."""

    @abc.abstractmethod
    def click(self, selector: str) -> bool:
        """Click an element."""

    @abc.abstractmethod
    def get_text(self, selector: str) -> str:
        """Get text content from an element."""

    @abc.abstractmethod
    def screenshot(self, name: str) -> ScreenshotResult:
        """Capture a screenshot."""

    @abc.abstractmethod
    def check_for_security_blocks(self) -> None:
        """Check for CAPTCHA, MFA, or authentication prompts."""


class MockBrowserSession(BrowserSession):
    """Mock browser session for testing without real browser."""

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._started = False
        self._current_url = ""
        self._form_data: dict[str, str] = {}
        self._screenshot_dir = Path(self.config.screenshot_dir)
        logger.info("Mock browser session created (environment=%s)", self.config.environment)

    def start(self) -> None:
        self._started = True
        logger.info("Mock browser session started")

    def stop(self) -> None:
        self._started = False
        self._form_data.clear()
        logger.info("Mock browser session stopped")

    def navigate(self, url: str) -> NavigationResult:
        self._current_url = url
        logger.info("Mock navigate to: %s", url)
        return NavigationResult(success=True, url=url, title="Mock Page")

    def find_element(self, selector: str) -> ElementInfo:
        logger.info("Mock find element: %s", selector)
        return ElementInfo(selector=selector, tag="input", found=True)

    def fill_field(self, selector: str, value: str) -> FillResult:
        self._form_data[selector] = value
        logger.info("Mock fill: %s = %s", selector, _redact_value(value))
        return FillResult(success=True, field=selector, value=value)

    def select_option(self, selector: str, value: str) -> FillResult:
        self._form_data[selector] = value
        logger.info("Mock select: %s = %s", selector, value)
        return FillResult(success=True, field=selector, value=value)

    def click(self, selector: str) -> bool:
        logger.info("Mock click: %s", selector)
        return True

    def get_text(self, selector: str) -> str:
        return self._form_data.get(selector, "")

    def screenshot(self, name: str) -> ScreenshotResult:
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self._screenshot_dir / f"{name}.txt"
        path.write_text(f"Mock screenshot: {name}\nURL: {self._current_url}\nForm data: {self._form_data}")
        logger.info("Mock screenshot saved: %s", path)
        return ScreenshotResult(success=True, path=str(path))

    def check_for_security_blocks(self) -> None:
        logger.info("Mock security check: no blocks detected")

    @property
    def form_data(self) -> dict[str, str]:
        """Return collected form data (for testing)."""
        return dict(self._form_data)


def _redact_value(value: str) -> str:
    """Redact sensitive values for logging."""
    if len(value) > 4:
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
    return "****"


def create_browser_session(
    environment: str = "sandbox",
    headless: bool = True,
) -> BrowserSession:
    """Factory function to create appropriate browser session."""
    config = BrowserConfig(headless=headless, environment=environment)
    # Always use mock in sandbox environment for safety
    if environment == "sandbox":
        return MockBrowserSession(config)
    # In production, would use PlaywrightBrowserSession
    # For now, raise to prevent accidental production use
    raise BrowserError("Production browser sessions are not yet implemented", recoverable=False)
