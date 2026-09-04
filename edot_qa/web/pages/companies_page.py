from __future__ import annotations

import re

from playwright.sync_api import Locator, TimeoutError, Error as PlaywrightError, expect

from edot_qa.reporting.allure_helpers import allure_step
from edot_qa.web.base_page import BasePage
from edot_qa.web.pages.company_manage_page import CompanyManagePage
from edot_qa.web.pages.register_company_wizard_page import RegisterCompanyWizardPage


class CompaniesPage(BasePage):
    @property
    def companies_navigation(self) -> Locator:
        return self.first_visible(
            self._companies_navigation_candidates(),
            "Companies navigation",
            timeout_ms=5_000,
        )

    @property
    def add_company_button(self) -> Locator:
        return self.first_visible(
            [
                ("button named + Add Company", self.page.get_by_role("button", name=re.compile(r"^\+?\s*Add Company$", re.I)).first),
                ("link named + Add Company", self.page.get_by_role("link", name=re.compile(r"^\+?\s*Add Company$", re.I)).first),
                # Text fallback is justified because the assignment names this exact button.
                ("assignment-required + Add Company text", self.page.get_by_text("+ Add Company", exact=True).first),
                ("assignment-required Add Company text", self.page.get_by_text("Add Company", exact=True).first),
            ],
            "+ Add Company action",
            timeout_ms=15_000,
        )

    def open(self) -> None:
        with allure_step("Open eSuite Companies page", page=self.page):
            if not self.page.url.rstrip("/").endswith("/companies"):
                if not self._try_click_companies_navigation():
                    self.page.goto("/companies")
            self.page.wait_for_load_state("domcontentloaded")
            self._wait_for_company_list()

    def open_register_company_wizard(self) -> RegisterCompanyWizardPage:
        with allure_step("Open Register Company wizard", page=self.page):
            self.open()
            self.add_company_button.click()
            wizard = RegisterCompanyWizardPage(self.page, self.settings)
            wizard.expect_open()
            return wizard

    def open_manage(self) -> CompanyManagePage:
        with allure_step("Open Companies Manage page", page=self.page):
            self.open()
            self.page.wait_for_load_state("domcontentloaded")
            manage_page = CompanyManagePage(self.page, self.settings)
            manage_page.expect_loaded()
            return manage_page

    def _try_back_to_company_list(self) -> bool:
        if "/profile" not in self.page.url:
            return False
        with allure_step("Return from company detail to Companies list", page=self.page):
            return self._try_back_link_to_company_list()

    def _try_back_link_to_company_list(self) -> bool:
        for back_link in (
            self.page.get_by_role("link", name=re.compile(r"Back to Company List", re.I)).first,
            # Text fallback is justified because eSuite profile page exposes this exact return action.
            self.page.get_by_text("Back to Company List", exact=True).first,
        ):
            try:
                back_link.click(timeout=5_000)
                self.page.wait_for_load_state("domcontentloaded")
                if "/profile" not in self.page.url:
                    return True
            except (PlaywrightError, TimeoutError):
                continue
        return False

    def _wait_for_company_list(self) -> None:
        self.first_visible(
            [
                ("button named + Add Company", self.page.get_by_role("button", name=re.compile(r"^\+?\s*Add Company$", re.I)).first),
                ("button named Manage Company", self.page.get_by_role("button", name=re.compile(r"^Manage Company$", re.I)).first),
                # Text fallback is justified because the eSuite company list exposes this exact section title.
                ("company list My Company text", self.page.get_by_text("My Company", exact=True).first),
            ],
            "company list",
            timeout_ms=5_000,
        )

    def _companies_navigation_candidates(self) -> list[tuple[str, Locator]]:
        return [
            ("navigation item with Companies text", self.page.get_by_role("link", name=re.compile(r"^Companies$", re.I)).first),
            ("button with Companies text", self.page.get_by_role("button", name=re.compile(r"^Companies$", re.I)).first),
            # Text fallback is justified because the assignment names this exact navigation item.
            ("assignment-required Companies text", self.page.get_by_text("Companies", exact=True).first),
        ]

    def _try_click_companies_navigation(self) -> bool:
        for _, locator in self._companies_navigation_candidates():
            try:
                expect(locator).to_be_visible(timeout=1_000)
                locator.click(timeout=2_000)
                return True
            except (AssertionError, PlaywrightError, TimeoutError):
                continue
        return False
