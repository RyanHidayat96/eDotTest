from __future__ import annotations

from playwright.sync_api import Page, expect


class DeliberateFailurePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def open_fixture_page(self) -> None:
        self.page.set_content(
            """
            <main>
              <h1>eDOT Deliberate Failure Harness</h1>
              <button data-testid="edot-real-submit">Real Submit</button>
            </main>
            """
        )

    def expect_missing_submit_locator_visible(self) -> None:
        # Deliberate evidence-only wrong locator. Enabled only by EDOT_DELIBERATE_FAILURE.
        expect(self.page.get_by_test_id("edot-deliberate-missing-submit")).to_be_visible(timeout=500)
