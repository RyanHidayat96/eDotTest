from __future__ import annotations

import re

from playwright.sync_api import Locator, expect

from edot_qa.web.base_page import BasePage


class DashboardPage(BasePage):
    def open(self) -> None:
        self.open_path("/")

    @property
    def welcome_back_greeting(self) -> Locator:
        heading = self.page.get_by_role("heading", name=re.compile(r"Welcome Back,", re.I)).first
        # Text fallback is justified because the assignment requires this exact dashboard copy.
        text = self.page.get_by_text("Welcome Back,", exact=False).first
        return self.first_visible(
            [
                ("heading named Welcome Back,", heading),
                ("assignment-required greeting text", text),
            ],
            "dashboard greeting",
            timeout_ms=15_000,
        )

    def expect_loaded(self) -> None:
        expect(self.welcome_back_greeting).to_be_visible()
