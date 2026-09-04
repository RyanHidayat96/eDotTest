from __future__ import annotations

import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, TimeoutError, expect

from edot_qa.reporting.allure_helpers import allure_step, attach_json, attach_text
from edot_qa.web.base_page import BasePage
from edot_qa.web.pages.company_detail_page import (
    CompanyDetailDataNotLoadedError,
    CompanyDetailPage,
    DETAIL_EMPTY_MAX_RELOADS,
    confirm_delete_if_needed,
)


DETAIL_ACTION = re.compile(r"^(Manage|Detail|View|Open|Lihat|Kelola)$", re.I)
DELETE_ACTION = re.compile(r"^(Delete|Hapus|Remove)$", re.I)
DETAIL_OPEN_ATTEMPTS_AFTER_EMPTY_REFRESH = 2
COMPANY_LIST_READY_SCRIPT = """
() => {
  const visible = (element) => {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const root = document.querySelector("[id$='-content-single_company']");
  if (!visible(root)) return false;
  return Array.from(root.querySelectorAll(".bg-card")).some(visible);
}
"""
COMPANY_TEXT_VISIBLE_SCRIPT = """
(companyName) => {
  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
  const visible = (element) => {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const root = document.querySelector("[id$='-content-single_company']") || document.body;
  const expected = normalize(companyName);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (normalize(node.nodeValue) === expected && visible(node.parentElement)) return true;
    node = walker.nextNode();
  }
  return false;
}
"""
COMPANY_ACTION_MARK_SCRIPT = """
(payload) => {
  const markerAttribute = "data-edot-company-action-target";
  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
  const visible = (element) => {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const enabled = (element) => {
    return !element.disabled && element.getAttribute("aria-disabled") !== "true";
  };
  const actionText = (element) => normalize(
    element.innerText ||
    element.textContent ||
    element.getAttribute("aria-label") ||
    element.getAttribute("title") ||
    element.value
  );
  const isCompanyCard = (element) => {
    if (!element || !element.classList) return false;
    return element.classList.contains("bg-card") &&
      element.classList.contains("text-card-foreground") &&
      element.classList.contains("p-5") &&
      String(element.className || "").includes("rounded");
  };
  const expectedName = normalize(payload.companyName);
  const actionRegex = new RegExp(payload.actionPattern, "i");
  const root = document.querySelector("[id$='-content-single_company']") || document.body;
  document.querySelectorAll(`[${markerAttribute}]`).forEach((element) => element.removeAttribute(markerAttribute));

  const nameElements = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (normalize(node.nodeValue) === expectedName && visible(node.parentElement)) {
      nameElements.push(node.parentElement);
    }
    node = walker.nextNode();
  }

  const candidates = [];
  for (const nameElement of nameElements) {
    let container = nameElement;
    let depth = 0;
    let companyCard = null;
    while (container && container !== document.body && depth <= 12) {
      if (!companyCard && isCompanyCard(container)) {
        companyCard = container;
        break;
      }
      container = container.parentElement;
      depth += 1;
    }

    if (companyCard) {
      const rect = companyCard.getBoundingClientRect();
      const actions = Array.from(companyCard.querySelectorAll("button, a, [role='button']"))
        .filter((element) => visible(element) && enabled(element) && actionRegex.test(actionText(element)));
      for (const action of actions) {
        candidates.push({
          action,
          depth,
          area: rect.width * rect.height,
          isCompanyCard: true,
          actionText: actionText(action),
          containerText: normalize(companyCard.textContent).slice(0, 240),
          tagName: companyCard.tagName,
          className: String(companyCard.className || "").slice(0, 160),
        });
      }
      continue;
    }

    container = nameElement;
    depth = 0;
    while (container && container !== document.body && depth <= 12) {
      const actions = Array.from(container.querySelectorAll("button, a, [role='button']"))
        .filter((element) => visible(element) && enabled(element) && actionRegex.test(actionText(element)));
      for (const action of actions) {
        const rect = container.getBoundingClientRect();
        candidates.push({
          action,
          depth,
          area: rect.width * rect.height,
          isCompanyCard: isCompanyCard(container),
          actionText: actionText(action),
          containerText: normalize(container.textContent).slice(0, 240),
          tagName: container.tagName,
          className: String(container.className || "").slice(0, 160),
        });
      }
      container = container.parentElement;
      depth += 1;
    }
  }

  candidates.sort(
    (left, right) => Number(right.isCompanyCard) - Number(left.isCompanyCard) ||
      left.depth - right.depth ||
      left.area - right.area
  );
  const selected = candidates[0];
  if (!selected) {
    return {
      found: false,
      companyName: expectedName,
      exactTextMatches: nameElements.length,
      reason: "no matching action inside nearest company container",
    };
  }

  selected.action.setAttribute(markerAttribute, payload.marker);
  selected.action.scrollIntoView({block: "center", inline: "nearest"});
  return {
    found: true,
    companyName: expectedName,
    exactTextMatches: nameElements.length,
    depth: selected.depth,
    area: selected.area,
    isCompanyCard: selected.isCompanyCard,
    actionText: selected.actionText,
    containerText: selected.containerText,
    tagName: selected.tagName,
    className: selected.className,
  };
}
"""
SEARCH_CONTROL_FILL_SCRIPT = """
(searchText) => {
  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
  const visible = (element) => {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const selectors = [
    "input[type='search']",
    "input[placeholder*='Search' i]",
    "input[aria-label*='Search' i]",
    "[role='searchbox']",
    "[data-testid*='search' i] input",
    "[data-testid*='company-search' i] input"
  ];
  const controls = selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
  const control = controls.find((element) => visible(element) && !element.disabled && !element.readOnly);
  if (!control) return {used: false, reason: "visible search input not found"};

  control.focus();
  const prototype = control.tagName.toLowerCase() === "textarea"
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
  if (descriptor && descriptor.set) {
    descriptor.set.call(control, searchText);
  } else {
    control.value = searchText;
  }
  control.dispatchEvent(new Event("input", {bubbles: true}));
  control.dispatchEvent(new Event("change", {bubbles: true}));
  control.dispatchEvent(new KeyboardEvent("keydown", {bubbles: true, key: "Enter", code: "Enter"}));
  control.dispatchEvent(new KeyboardEvent("keyup", {bubbles: true, key: "Enter", code: "Enter"}));
  return {
    used: true,
    value: normalize(control.value),
    placeholder: control.getAttribute("placeholder") || "",
    ariaLabel: control.getAttribute("aria-label") || "",
  };
}
"""


class CompanyManagePage(BasePage):
    @property
    def heading(self) -> Locator:
        return self.first_visible(
            self._heading_candidates(),
            "Companies Manage page",
            timeout_ms=5_000,
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
            timeout_ms=1_500,
        )

    def expect_loaded(self) -> None:
        with allure_step("Verify Companies Manage page loaded", page=self.page):
            expect(self.heading).to_be_visible(timeout=5_000)

    def is_loaded(self, *, timeout_ms: int = 1_000) -> bool:
        if "/manage-companies" in self.page.url and "/profile" not in self.page.url:
            return True
        for _, locator in self._heading_candidates():
            try:
                expect(locator).to_be_visible(timeout=timeout_ms)
                return True
            except AssertionError:
                continue
        return False

    def search_company(self, company_name: str) -> None:
        with allure_step("Search company in Manage list", page=self.page, data={"search_text": company_name}):
            result = self._try_fast_search(company_name)
            if not result.get("used"):
                attach_text("company-manage-search-not-used", result.get("reason", "visible search input not found"))
                return
            try:
                self.page.keyboard.press("Enter")
            except PlaywrightError:
                pass
            attach_json("company-manage-search-used", result)
            self._wait_after_table_action()

    def expect_company_present(self, company_name: str) -> None:
        with allure_step("Verify company exists in Manage list", page=self.page, data={"company_name": company_name}):
            self.search_company(company_name)
            # Tier 2: created company must exist in Manage results after submit.
            self._expect_company_text_visible(company_name, timeout_ms=5_000)
            attach_json("company-manage-record-present", {"company_name": company_name})

    def expect_company_absent(self, company_name: str, company_id: str | None = None) -> None:
        with allure_step(
            "Verify deleted company is absent from Companies page",
            page=self.page,
            data={"company_name": company_name, "company_id": company_id},
        ):
            self._reload_companies_page()
            self.search_company(company_name)
            self._expect_exact_text_absent("company name", company_name)

            if company_id:
                self.search_company(company_id)
                self._expect_exact_text_absent("company id", company_id)

            attach_json("company-cleanup-record-absent", {"company_name": company_name, "company_id": company_id})

    def open_company_detail(self, company_name: str) -> CompanyDetailPage:
        with allure_step("Open company detail from Manage list", page=self.page, data={"company_name": company_name}):
            errors: list[str] = []
            for attempt in range(1, DETAIL_OPEN_ATTEMPTS_AFTER_EMPTY_REFRESH + 1):
                self.search_company(company_name)
                try:
                    self._expect_company_text_visible(company_name, timeout_ms=5_000)
                    with allure_step(
                        "Click Manage action for company",
                        page=self.page,
                        data={"company_name": company_name, "attempt": attempt},
                    ):
                        marker = f"detail-{attempt}"
                        target = self._mark_company_action(company_name, DETAIL_ACTION.pattern, marker)
                        attach_json("company-manage-action-target", target)
                        if not target.get("found"):
                            raise AssertionError(
                                f"Could not find Manage action beside company {company_name!r}: {target}"
                            )
                        self._click_marked_company_action(marker, wait_for_profile=True)

                    self._wait_after_table_action()
                    detail = CompanyDetailPage(self.page, self.settings)
                    max_reloads = DETAIL_EMPTY_MAX_RELOADS if attempt == 1 else 0
                    detail.refresh_until_company_name_loaded(company_name, max_reloads=max_reloads)
                    attach_json("company-detail-opened", {"company_name": company_name})
                    return detail
                except CompanyDetailDataNotLoadedError as error:
                    errors.append(f"attempt {attempt}: {error}")
                    if attempt < DETAIL_OPEN_ATTEMPTS_AFTER_EMPTY_REFRESH:
                        attach_json(
                            "company-detail-reopen-after-empty-refresh-limit",
                            {
                                "company_name": company_name,
                                "attempt": attempt,
                                "reloads_used": DETAIL_EMPTY_MAX_RELOADS,
                                "next_action": "return to Companies and click Manage again",
                            },
                        )
                        self._reload_companies_page()
                        continue
                    break
                except (AssertionError, PlaywrightError, TimeoutError) as error:
                    errors.append(f"attempt {attempt}: {error}")
                    if "/profile" in self.page.url:
                        break
                    self.page.wait_for_load_state("domcontentloaded")
            raise AssertionError(f"Could not open detail for company {company_name!r}; {' | '.join(errors)}")

    def delete_company_if_present(self, company_name: str) -> None:
        with allure_step("Delete company if present", page=self.page, data={"company_name": company_name}):
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

    def _heading_candidates(self) -> list[tuple[str, Locator]]:
        return [
            ("heading named Manage", self.page.get_by_role("heading", name=re.compile(r"Manage", re.I)).first),
            ("region named Manage", self.page.get_by_role("region", name=re.compile(r"Manage", re.I)).first),
            ("button named + Add Company", self.page.get_by_role("button", name=re.compile(r"^\+?\s*Add Company$", re.I)).first),
            ("button named Manage Company", self.page.get_by_role("button", name=re.compile(r"^Manage Company$", re.I)).first),
            ("company list My Company text", self.page.get_by_text("My Company", exact=True).first),
            # Text fallback is justified because the assignment names this exact Companies sub-page.
            ("assignment-required Manage text", self.page.get_by_text("Manage", exact=True).first),
        ]

    def _expect_exact_text_absent(
        self,
        label: str,
        identifier: str,
    ) -> None:
        with allure_step(
            f"Verify deleted company {label} is not visible",
            page=self.page,
            data={label.replace(" ", "_"): identifier},
        ):
            if self._is_exact_text_visible_now(identifier):
                raise AssertionError(f"Deleted company {label} {identifier!r} is still visible in Companies results")

    def _reload_companies_page(self) -> None:
        with allure_step("Reload Companies page", page=self.page):
            self.page.goto("/companies")
            self.page.wait_for_load_state("domcontentloaded")
            self.first_visible(
                [
                    ("button named + Add Company", self.page.get_by_role("button", name=re.compile(r"^\+?\s*Add Company$", re.I)).first),
                    ("button named Manage Company", self.page.get_by_role("button", name=re.compile(r"^Manage Company$", re.I)).first),
                    # Text fallback is justified because the eSuite company list exposes this exact section title.
                    ("company list My Company text", self.page.get_by_text("My Company", exact=True).first),
                ],
                "company list after cleanup",
                timeout_ms=10_000,
            )
            self.page.wait_for_function(COMPANY_LIST_READY_SCRIPT, timeout=5_000)

    def _is_company_visible(self, company_name: str, timeout_ms: int) -> bool:
        return self._is_exact_text_visible(company_name, timeout_ms=timeout_ms)

    def _try_delete_from_manage(self, company_name: str) -> bool:
        with allure_step("Try delete company from Manage list", page=self.page, data={"company_name": company_name}):
            target = self._mark_company_action(company_name, DELETE_ACTION.pattern, "delete")
            attach_json("company-delete-action-target", target)
            if not target.get("found"):
                return False
            self._click_marked_company_action("delete", wait_for_profile=False)
            self._confirm_delete_if_needed()
            self._wait_after_table_action()
            return True

    def _expect_company_text_visible(self, company_name: str, timeout_ms: int) -> None:
        try:
            self.page.wait_for_function(COMPANY_TEXT_VISIBLE_SCRIPT, arg=company_name, timeout=timeout_ms)
        except TimeoutError as error:
            raise AssertionError(f"Company {company_name!r} is not visible in Companies results") from error

    def _is_exact_text_visible(self, text: str, timeout_ms: int) -> bool:
        try:
            self.page.wait_for_function(COMPANY_TEXT_VISIBLE_SCRIPT, arg=text, timeout=timeout_ms)
            return True
        except TimeoutError:
            return False

    def _is_exact_text_visible_now(self, text: str) -> bool:
        try:
            return bool(self.page.evaluate(COMPANY_TEXT_VISIBLE_SCRIPT, text))
        except PlaywrightError as error:
            raise AssertionError(f"Could not evaluate company text visibility for {text!r}") from error

    def _try_fast_search(self, search_text: str) -> dict[str, object]:
        try:
            result = self.page.evaluate(SEARCH_CONTROL_FILL_SCRIPT, search_text)
        except PlaywrightError as error:
            return {"used": False, "reason": str(error)}
        return result if isinstance(result, dict) else {"used": False, "reason": "unexpected search result"}

    def _mark_company_action(self, company_name: str, action_pattern: str, marker: str) -> dict[str, object]:
        try:
            result = self.page.evaluate(
                COMPANY_ACTION_MARK_SCRIPT,
                {
                    "companyName": company_name,
                    "actionPattern": action_pattern,
                    "marker": marker,
                },
            )
        except PlaywrightError as error:
            return {"found": False, "companyName": company_name, "reason": str(error)}
        return result if isinstance(result, dict) else {"found": False, "companyName": company_name, "reason": "unexpected action result"}

    def _click_marked_company_action(self, marker: str, *, wait_for_profile: bool) -> None:
        locator = self.page.locator(f"[data-edot-company-action-target='{marker}']").first
        expect(locator).to_be_visible(timeout=1_000)
        locator.click(timeout=5_000)
        if wait_for_profile:
            self.page.wait_for_url(lambda url: "/profile" in url, timeout=10_000)

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
