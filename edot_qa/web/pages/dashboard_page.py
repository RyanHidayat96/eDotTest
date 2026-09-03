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
        try:
            expect(heading).to_be_visible(timeout=1_000)
            return heading
        except AssertionError:
            pass

        # Text fallback is justified because the assignment requires this exact dashboard copy.
        text = self.page.get_by_text("Welcome Back,", exact=False).first
        expect(text).to_be_visible(timeout=15_000)
        return text

    def expect_loaded(self) -> None:
        expect(self.welcome_back_greeting).to_be_visible()
