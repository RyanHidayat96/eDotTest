from __future__ import annotations

import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, TimeoutError, expect

from edot_qa.reporting.allure_helpers import attach_json, attach_text
from edot_qa.web.base_page import BasePage
from edot_qa.web.pages.company_detail_page import CompanyDetailPage, confirm_delete_if_needed


DETAIL_ACTION = re.compile(r"^(Manage|Detail|View|Open|Lihat|Kelola)$", re.I)
DELETE_ACTION = re.compile(r"^(Delete|Hapus|Remove)$", re.I)


class CompanyManagePage(BasePage):
    @property
    def heading(self) -> Locator:
        return self.first_visible(
            [
                ("heading named Manage", self.page.get_by_role("heading", name=re.compile(r"Manage", re.I)).first),
                ("region named Manage", self.page.get_by_role("region", name=re.compile(r"Manage", re.I)).first),
                # Text fallback is justified because the assignment names this exact Companies sub-page.
                ("assignment-required Manage text", self.page.get_by_text("Manage", exact=True).first),
            ],
            "Companies Manage page",
            timeout_ms=15_000,
        )

    @property
    def search_control(self) -> Locator:
        return self.first_visible(
            [
                ("data-testid company-search", self.page.get_by_test_id("company-search").first),
                ("data-testid search", self.page.get_by_test_id("search").first),
                ("searchbox", self.page.get_by_role("searchbox").first),
                ("textbox named Search", self.page.get_by_role("textbox", name=re.compile(r"Search", re.I)).first),
                ("labelled Search", self.page.get_by_label(re.compile(r"Search", re.I)).first),
                ("placeholder Search", self.page.get_by_placeholder(re.compile(r"Search", re.I)).first),
                ("stable search input", self.page.locator(stable_search_selector()).first),
            ],
            "company search control",
            timeout_ms=5_000,
        )

    def expect_loaded(self) -> None:
        expect(self.heading).to_be_visible(timeout=15_000)

    def search_company(self, company_name: str) -> None:
        if self.page.locator("input").count() == 0:
            attach_text("company-manage-search-not-used", "Company list exposes no search input; verifying visible card list instead.")
            return
        try:
            search = self.search_control
        except AssertionError as error:
            attach_text("company-manage-search-not-used", str(error))
            return
        search.fill(company_name)
        try:
            search.press("Enter")
        except PlaywrightError:
            pass
        self._wait_after_table_action()

    def expect_company_present(self, company_name: str) -> None:
        self.search_company(company_name)
        # Tier 2: created company must exist in Manage results after submit.
        expect(self._company_record(company_name)).to_be_visible(timeout=15_000)
        attach_json("company-manage-record-present", {"company_name": company_name})

    def expect_company_absent(self, company_name: str) -> None:
        self.search_company(company_name)
        errors: list[str] = []
        for description, locator in self._company_record_candidates(company_name):
            try:
                # Tier 2: cleanup must prove deleted company is gone from Manage results.
                expect(locator).not_to_be_visible(timeout=15_000)
            except AssertionError as error:
                errors.append(f"{description}: {error}")
        if errors:
            raise AssertionError(f"Deleted company {company_name!r} is still visible in Manage results")
        attach_json("company-cleanup-record-absent", {"company_name": company_name})

    def open_company_detail(self, company_name: str) -> CompanyDetailPage:
        self.search_company(company_name)
        errors: list[str] = []
        for attempt in range(1, 4):
            try:
                record = self._company_record(company_name)
                record.scroll_into_view_if_needed(timeout=5_000)
                try:
                    record.hover(timeout=2_000)
                except PlaywrightError:
                    pass

                if not self._try_open_detail_from_record(record):
                    self._click_and_wait_for_detail(record)

                self._wait_after_table_action()
                detail = CompanyDetailPage(self.page, self.settings)
                detail.expect_loaded_for(company_name)
                attach_json("company-detail-opened", {"company_name": company_name})
                return detail
            except (AssertionError, PlaywrightError, TimeoutError) as error:
                errors.append(f"attempt {attempt}: {error}")
                if "/profile" in self.page.url:
                    break
                self.page.wait_for_load_state("domcontentloaded")
        raise AssertionError(f"Could not open detail for company {company_name!r}; {' | '.join(errors)}")

    def delete_company_if_present(self, company_name: str) -> None:
        self.search_company(company_name)
        if not self._is_company_visible(company_name, timeout_ms=5_000):
            attach_json("company-cleanup-skipped", {"company_name": company_name, "reason": "not_found"})
            return

        attach_json("company-cleanup-started", {"company_name": company_name})
        if self._try_delete_from_manage(company_name):
            attach_json("company-cleanup-delete-requested", {"company_name": company_name, "source": "manage"})
            return

        detail = self.open_company_detail(company_name)
        detail.delete_current_company()
        attach_json("company-cleanup-delete-requested", {"company_name": company_name, "source": "detail"})

    def _company_record(self, company_name: str, timeout_ms: int = 15_000) -> Locator:
        return self.first_visible(
            self._company_record_candidates(company_name),
            f"company record {company_name}",
            timeout_ms=timeout_ms,
        )

    def _company_record_candidates(self, company_name: str) -> list[tuple[str, Locator]]:
        company_name_pattern = re.compile(re.escape(company_name), re.I)
        return [
            (
                "company card containing company name and Manage action",
                # Text fallback is justified because company cards expose persisted company names as visible card text.
                self.page.locator("div.rounded-lg.border")
                .filter(has_text=company_name_pattern)
                .filter(has=self.page.get_by_role("button", name=DETAIL_ACTION))
                .first,
            ),
            ("row containing company name", self.page.get_by_role("row", name=company_name_pattern).first),
            ("link named company", self.page.get_by_role("link", name=company_name_pattern).first),
            ("button named company", self.page.get_by_role("button", name=company_name_pattern).first),
            # Text fallback is justified because created company name is the exact persisted value under test.
            ("exact company-name text", self.page.get_by_text(company_name, exact=True).first),
        ]

    def _is_company_visible(self, company_name: str, timeout_ms: int) -> bool:
        for _, locator in self._company_record_candidates(company_name):
            try:
                expect(locator).to_be_visible(timeout=timeout_ms)
                return True
            except AssertionError:
                continue
        return False

    def _try_open_detail_from_record(self, record: Locator) -> bool:
        for _, locator in self._detail_action_candidates(record):
            try:
                expect(locator).to_be_visible(timeout=2_000)
                self._click_and_wait_for_detail(locator)
                return True
            except (AssertionError, PlaywrightError, TimeoutError):
                continue
        return False

    def _click_and_wait_for_detail(self, locator: Locator) -> None:
        before_url = self.page.url
        locator.click(timeout=5_000)
        self.page.wait_for_url(lambda url: "/profile" in url or url != before_url, timeout=10_000)

    def _try_delete_from_manage(self, company_name: str) -> bool:
        record = self._company_record(company_name, timeout_ms=5_000)
        try:
            record.hover(timeout=2_000)
        except PlaywrightError:
            pass

        for _, locator in self._delete_action_candidates(record):
            try:
                expect(locator).to_be_visible(timeout=2_000)
                locator.click()
                self._confirm_delete_if_needed()
                self._wait_after_table_action()
                return True
            except (AssertionError, PlaywrightError, TimeoutError):
                continue
        return False

    def _detail_action_candidates(self, record: Locator) -> list[tuple[str, Locator]]:
        return [
            ("row Manage button", record.get_by_role("button", name=DETAIL_ACTION).first),
            ("row Manage link", record.get_by_role("link", name=DETAIL_ACTION).first),
            ("row stable manage action", record.locator(stable_action_selector("manage")).first),
            ("row stable detail action", record.locator(stable_action_selector("detail")).first),
        ]

    def _delete_action_candidates(self, record: Locator) -> list[tuple[str, Locator]]:
        return [
            ("row Delete button", record.get_by_role("button", name=DELETE_ACTION).first),
            ("row Delete link", record.get_by_role("link", name=DELETE_ACTION).first),
            ("row stable delete action", record.locator(stable_action_selector("delete")).first),
        ]

    def _confirm_delete_if_needed(self) -> None:
        confirm_delete_if_needed(self.page)

    def _wait_after_table_action(self) -> None:
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=2_000)
        except TimeoutError:
            pass


def stable_search_selector() -> str:
    return (
        "input[name='search'], input[id='search'], "
        "input[aria-label='Search'], input[placeholder='Search']"
    )


def stable_action_selector(action_name: str) -> str:
    return (
        f"button[name='{action_name}'], button[id='{action_name}'], "
        f"a[name='{action_name}'], a[id='{action_name}'], "
        f"button[aria-label='{action_name}'], a[aria-label='{action_name}']"
    )
