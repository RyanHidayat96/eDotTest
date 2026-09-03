from __future__ import annotations

import re

from playwright.sync_api import Locator

from edot_qa.web.base_page import BasePage
from edot_qa.web.pages.company_manage_page import CompanyManagePage
from edot_qa.web.pages.register_company_wizard_page import RegisterCompanyWizardPage


class CompaniesPage(BasePage):
    @property
    def companies_navigation(self) -> Locator:
        return self.first_visible(
            [
                ("navigation item with Companies text", self.page.get_by_role("link", name=re.compile(r"^Companies$", re.I)).first),
                ("button with Companies text", self.page.get_by_role("button", name=re.compile(r"^Companies$", re.I)).first),
                # Text fallback is justified because the assignment names this exact navigation item.
                ("assignment-required Companies text", self.page.get_by_text("Companies", exact=True).first),
            ],
            "Companies navigation",
            timeout_ms=15_000,
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

    @property
    def manage_navigation(self) -> Locator:
        return self.first_visible(
            [
                ("tab named Manage", self.page.get_by_role("tab", name=re.compile(r"^Manage$", re.I)).first),
                ("link named Manage", self.page.get_by_role("link", name=re.compile(r"^Manage$", re.I)).first),
                ("button named Manage", self.page.get_by_role("button", name=re.compile(r"^Manage$", re.I)).first),
                # Text fallback is justified because the assignment names this exact Companies sub-page.
                ("assignment-required Manage text", self.page.get_by_text("Manage", exact=True).first),
            ],
            "Companies Manage navigation",
            timeout_ms=15_000,
        )

    def open(self) -> None:
        self.companies_navigation.click()
        self.page.wait_for_load_state("domcontentloaded")

    def open_register_company_wizard(self) -> RegisterCompanyWizardPage:
        self.open()
        self.add_company_button.click()
        wizard = RegisterCompanyWizardPage(self.page, self.settings)
        wizard.expect_open()
        return wizard

    def open_manage(self) -> CompanyManagePage:
        self.open()
        self.manage_navigation.click()
        self.page.wait_for_load_state("domcontentloaded")
        return CompanyManagePage(self.page, self.settings)
