from __future__ import annotations

from edot_qa.reporting.allure_helpers import _capture_page_screenshot


class FlakyScreenshotPage:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.waits: list[int] = []

    def screenshot(self, **options: object) -> bytes:
        self.calls.append(options)
        if len(self.calls) < 3:
            raise RuntimeError("Protocol error (Page.captureScreenshot): Unable to capture screenshot")
        return b"png"

    def wait_for_timeout(self, delay_ms: int) -> None:
        self.waits.append(delay_ms)


def test_capture_page_screenshot_retries_transient_playwright_protocol_error() -> None:
    page = FlakyScreenshotPage()

    image, error = _capture_page_screenshot(page, full_page=True)

    assert image == b"png"
    assert error is None
    assert page.calls[0] == {"full_page": True, "timeout": 10_000}
    assert page.calls[1]["full_page"] is False
    assert page.waits == [150]
