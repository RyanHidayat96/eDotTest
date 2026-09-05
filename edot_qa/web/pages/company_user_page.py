from __future__ import annotations

import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, TimeoutError, expect

from edot_qa.reporting.allure_helpers import (
    allure_step,
    attach_json,
    attach_page_evidence,
    attach_text,
    show_dev_inputs_in_reports,
)
from edot_qa.web.base_page import BasePage
from edot_qa.web.company_user import CompanyUserData


COMPANY_USER_TAB = re.compile(r"^Company User$", re.I)
ADD_USER = re.compile(r"^\+?\s*Add User$", re.I)
SUBMIT_DATA = re.compile(r"^Submit Data$", re.I)
BRANCH_NAME_VISIBLE_SCRIPT = """
(branchName) => {
  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
  const visible = (element) => {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const expected = normalize(branchName);
  const dialogs = Array.from(document.querySelectorAll("[role='dialog']")).filter(visible);
  const dialog = dialogs.reverse().find((element) => normalize(element.textContent).includes("Add Company User"));
  if (!dialog) return false;
  const walker = document.createTreeWalker(dialog, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (normalize(node.nodeValue) === expected && visible(node.parentElement)) return true;
    node = walker.nextNode();
  }
  return false;
}
"""


class CompanyUserPage(BasePage):
    @property
    def add_user_button(self) -> Locator:
        return self.first_visible(
            [
                ("button named + Add User", self.page.get_by_role("button", name=ADD_USER).first),
                # Text fallback is justified because eSuite exposes this exact Company User action.
                ("Company User + Add User text", self.page.get_by_text("+ Add User", exact=True).first),
                ("Company User Add User text", self.page.get_by_text("Add User", exact=True).first),
            ],
            "+ Add User action",
            timeout_ms=10_000,
        )

    def open(self) -> "CompanyUserPage":
        with allure_step("Open Company User tab", page=self.page, screenshot=True):
            self.first_visible(
                [
                    ("Company User nav text", self.page.get_by_text(COMPANY_USER_TAB).first),
                    ("Company User tab", self.page.get_by_role("tab", name=COMPANY_USER_TAB).first),
                ],
                "Company User tab",
                timeout_ms=10_000,
            ).click()
            self.expect_loaded()
            return self

    def expect_loaded(self) -> None:
        with allure_step("Verify Company User list loaded", page=self.page, screenshot=True):
            self.first_visible(
                [
                    ("Company User count text", self.page.get_by_text(re.compile(r"Company User \\(\\d+/\\d+\\)", re.I)).first),
                    ("List User tab", self.page.get_by_role("tab", name=re.compile(r"^List User$", re.I)).first),
                    ("+ Add User button", self.page.get_by_role("button", name=ADD_USER).first),
                ],
                "Company User list",
                timeout_ms=10_000,
            )

    def create_user(self, user: CompanyUserData) -> None:
        with allure_step(
            "Create company user for eWork login",
            page=self.page,
            screenshot=True,
        ):
            dialog = self.open_add_user_dialog()
            self.fill_general_info(dialog, user)
            self.add_branch(dialog, user.branch_name)
            self.submit_user(dialog)
            # Tier 2: created user must be visible in the Company User table before handoff login.
            self.expect_user_present(user)

    def open_add_user_dialog(self) -> Locator:
        with allure_step("Open Add Company User dialog", page=self.page, screenshot=True):
            self.add_user_button.click()
            dialog = self.add_user_dialog()
            expect(dialog).to_be_visible(timeout=10_000)
            return dialog

    def fill_general_info(self, dialog: Locator, user: CompanyUserData) -> None:
        with allure_step(
            "Fill Company User general info",
            page=self.page,
            force=True,
        ):
            self.select_active_status(dialog)
            dialog.get_by_placeholder("Input Name").fill(user.name)
            dialog.get_by_placeholder("Input Username").fill(user.username)
            dialog.get_by_placeholder("Input Employee ID").fill(user.employee_id)
            dialog.get_by_placeholder("Input Email").fill(user.email)
            dialog.get_by_placeholder("Input Phone").fill(user.phone)
            dialog.get_by_placeholder("Input Password").fill(user.password)
            attach_json("Inputs", _company_user_input_payload(user), redact=False)
            attach_page_evidence("Company User general info input", self.page, screenshot=True)
            next_button = dialog.get_by_role("button", name=re.compile(r"^Next$", re.I)).first
            expect(next_button).to_be_enabled(timeout=5_000)
            next_button.click()
            self.expect_branch_step(dialog)

    def select_active_status(self, dialog: Locator) -> None:
        radio_buttons = dialog.locator("button[role='radio']")
        first_radio = radio_buttons.first
        expect(first_radio).to_be_visible(timeout=5_000)
        if first_radio.get_attribute("aria-checked") != "true":
            first_radio.click()

    def expect_branch_step(self, dialog: Locator) -> None:
        expect(dialog.get_by_text("Branch", exact=True).first).to_be_visible(timeout=10_000)
        expect(dialog.get_by_role("button", name=re.compile(r"^Add Branch$", re.I)).first).to_be_visible(timeout=10_000)

    def add_branch(self, dialog: Locator, branch_name: str) -> None:
        with allure_step(
            "Add Company User branch access",
            page=self.page,
            input_data={"branch_name": branch_name},
            screenshot=True,
        ):
            dialog.get_by_role("button", name=re.compile(r"^Add Branch$", re.I)).first.click()
            branch_dialog = self.add_branch_dialog(branch_name)
            expect(branch_dialog).to_be_visible(timeout=10_000)
            self.select_first_branch(branch_dialog)
            branch_dialog.get_by_role("button", name=re.compile(r"^Add$", re.I)).last.click()
            self.page.wait_for_function(BRANCH_NAME_VISIBLE_SCRIPT, arg=branch_name, timeout=10_000)
            expect(dialog.get_by_role("button", name=SUBMIT_DATA).first).to_be_enabled(timeout=5_000)

    def submit_user(self, dialog: Locator) -> None:
        with allure_step("Submit Company User", page=self.page, screenshot=True):
            dialog.get_by_role("button", name=SUBMIT_DATA).first.click()
            try:
                expect(dialog).not_to_be_visible(timeout=15_000)
            except AssertionError as error:
                attach_text("company-user-submit-dialog-text", dialog.inner_text(timeout=2_000))
                raise AssertionError("Company User dialog stayed open after Submit Data") from error
            self.page.wait_for_load_state("domcontentloaded")

    def expect_user_present(self, user: CompanyUserData) -> None:
        with allure_step(
            "Verify company user appears in list",
            page=self.page,
            data=user.as_handoff_payload(),
            screenshot=True,
        ):
            self.search_user(user.username)
            expect(self.page.get_by_text(user.username, exact=True).first).to_be_visible(timeout=10_000)
            expect(self.page.get_by_text(user.email, exact=True).first).to_be_visible(timeout=10_000)
            attach_json("company-user-created", user.as_handoff_payload())

    def search_user(self, username: str) -> None:
        try:
            search = self.page.get_by_placeholder("Search").first
            expect(search).to_be_visible(timeout=2_000)
            search.fill(username)
            self.page.keyboard.press("Enter")
            attach_json("Inputs", {"fields": {"company_user_search": username}})
            attach_page_evidence("Company User search result", self.page, screenshot=True)
        except (AssertionError, PlaywrightError, TimeoutError):
            return

    def add_user_dialog(self) -> Locator:
        return self.page.get_by_role("dialog").filter(has_text="Add Company User").last

    def add_branch_dialog(self, branch_name: str) -> Locator:
        return self.page.get_by_role("dialog").filter(has_text="Add Branch").filter(has_text=branch_name).last

    @staticmethod
    def select_first_branch(branch_dialog: Locator) -> None:
        checkbox = branch_dialog.locator("button[role='checkbox']").first
        expect(checkbox).to_be_visible(timeout=5_000)
        if checkbox.get_attribute("aria-checked") != "true":
            checkbox.click()


def _company_user_input_payload(user: CompanyUserData) -> dict[str, object]:
    password = user.password if show_dev_inputs_in_reports() else "<redacted>"
    return {
        "fields": {
            "Name": user.name,
            "Username": user.username,
            "Employee ID": user.employee_id,
            "Email": user.email,
            "Phone": user.phone,
            "Password": password,
        }
    }
