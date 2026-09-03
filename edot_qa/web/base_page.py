from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from playwright.sync_api import Locator, Page, expect

from edot_qa.config import Settings


@dataclass
class BasePage:
    page: Page
    settings: Settings

    def open_path(self, path: str = "/") -> None:
        self.page.goto(path)

    def wait_for_app_network_idle(self) -> None:
        self.page.wait_for_load_state("networkidle")

    def first_visible(
        self,
        candidates: Iterable[tuple[str, Locator]],
        description: str,
        timeout_ms: int = 3_000,
    ) -> Locator:
        missed: list[str] = []
        for label, locator in candidates:
            try:
                expect(locator).to_be_visible(timeout=timeout_ms)
                return locator
            except AssertionError:
                missed.append(label)
        raise AssertionError(f"Could not find visible {description}; tried: {', '.join(missed)}")
