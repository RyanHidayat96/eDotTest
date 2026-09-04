from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, TimeoutError, expect

from edot_qa.reporting.allure_helpers import allure_step, attach_json
from edot_qa.web.base_page import BasePage
from edot_qa.web.company_registration import CompanyRegistrationData


DELETE_ACTION = re.compile(r"^(Delete|Hapus|Remove)$", re.I)
CONFIRM_DELETE_ACTION = re.compile(r"^(Confirm|Delete|Hapus|Yes|Ya|OK)$", re.I)
DELETE_AGREEMENT = re.compile(r"I understand\s*&\s*agree to delete", re.I)
DETAIL_EMPTY_REFRESH_TIMEOUT_MS = 2_000
DETAIL_EMPTY_MAX_RELOADS = 5
DETAIL_COMPANY_NAME_FIELD_VALUE_SCRIPT = """
() => {
  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
  const visible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const meaningful = (value) => {
    const text = normalize(value);
    return (
      text.length > 0 &&
      !/^choose\\b/i.test(text) &&
      !/^input\\b/i.test(text) &&
      !/^select\\b/i.test(text)
    );
  };
  const fieldValue = (element) => normalize(
    element.value ||
    element.textContent ||
    element.getAttribute("value") ||
    element.getAttribute("aria-label") ||
    element.getAttribute("title")
  );
  const controlsFrom = (root) => Array.from(
    root?.querySelectorAll?.("input, textarea, [role='textbox'], [contenteditable='true']") || []
  );
  const directControls = Array.from(
    document.querySelectorAll(
      [
        "input[placeholder*='Company Name' i]",
        "textarea[placeholder*='Company Name' i]",
        "input[name*='companyName' i]",
        "textarea[name*='companyName' i]",
        "input[name*='company_name' i]",
        "textarea[name*='company_name' i]",
        "input[id*='companyName' i]",
        "textarea[id*='companyName' i]",
        "input[id*='company_name' i]",
        "textarea[id*='company_name' i]",
        "[data-testid*='company-name' i]",
        "[data-testid*='companyName' i]",
      ].join(",")
    )
  );
  const labeledControls = [];
  const labels = Array.from(document.querySelectorAll("label, div, span, p"))
    .filter((element) => visible(element) && /^Company Name\\*?$/i.test(normalize(element.textContent)));
  for (const label of labels) {
    const roots = [
      label,
      label.parentElement,
      label.parentElement?.parentElement,
      label.closest("label"),
      label.closest("div"),
      label.closest("section"),
      label.nextElementSibling,
    ].filter(Boolean);
    for (const root of roots) {
      labeledControls.push(...controlsFrom(root));
    }
  }
  for (const element of [...directControls, ...labeledControls]) {
    if (!visible(element)) continue;
    const value = fieldValue(element);
    if (meaningful(value)) return value;
  }
  return "";
}
"""
DETAIL_COMPANY_NAME_FIELD_SCRIPT = """
(payload) => {
  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
  const expected = normalize(payload.expected);
  const visible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const meaningful = (value) => {
    const text = normalize(value);
    return (
      text.length > 0 &&
      !/^choose\\b/i.test(text) &&
      !/^input\\b/i.test(text) &&
      !/^select\\b/i.test(text)
    );
  };
  const fields = Array.from(
    document.querySelectorAll(
      [
        "input[placeholder='Input Company Name']",
        "textarea[placeholder='Input Company Name']",
        "input[name='companyName']",
        "textarea[name='companyName']",
        "input[name='company_name']",
        "textarea[name='company_name']",
        "input[id='companyName']",
        "textarea[id='companyName']",
        "input[id='company_name']",
        "textarea[id='company_name']",
        "[data-testid='company-name']",
        "[data-testid='companyName']",
      ].join(",")
    )
  );
  return fields.some((element) => {
    if (!visible(element)) return false;
    const rawValue =
      element.value ||
      element.textContent ||
      element.getAttribute("aria-label") ||
      element.getAttribute("title");
    const value = normalize(rawValue);
    if (payload.requireExpected) {
      return expected.length > 0 && (value === expected || value.includes(expected));
    }
    return meaningful(value);
  });
}
"""

@dataclass(frozen=True)
class DetailFieldSpec:
    label: str
    test_ids: tuple[str, ...]
    stable_names: tuple[str, ...]
    placeholders: tuple[str, ...] = ()


class CompanyDetailDataNotLoadedError(AssertionError):
    """Raised when eSuite opens an empty company detail form after Manage."""


class CompanyDetailPage(BasePage):
    name = DetailFieldSpec(
        "name",
        ("company-name", "companyName"),
        ("companyName", "company_name", "name"),
        ("Input Company Name",),
    )
    company_id = DetailFieldSpec(
        "company id",
        ("company-id", "companyId"),
        ("companyId", "company_id", "id"),
        ("Input Company ID",),
    )
    industry_type = DetailFieldSpec(
        "industry type",
        ("industry-type", "industryType"),
        ("industryType", "industry_type", "industry"),
    )
    company_type = DetailFieldSpec(
        "company type",
        ("company-type", "companyType"),
        ("companyType", "company_type", "type"),
    )
    address = DetailFieldSpec(
        "address",
        ("street-address", "streetAddress", "address"),
        ("streetAddress", "address"),
        ("Input Company Address",),
    )
    postal_code = DetailFieldSpec(
        "postal code",
        ("postal-code", "postalCode"),
        ("postalCode", "postal_code", "zip"),
        ("Choose Postal Code",),
    )
    email = DetailFieldSpec("email", ("company-email", "email"), ("email",), ("Input Email",))
    phone = DetailFieldSpec(
        "phone",
        ("company-phone", "phone"),
        ("phone", "phoneNumber", "phone_number"),
        ("Input Mobile Number",),
    )

    def expect_loaded_for(self, company_name: str) -> None:
        with allure_step("Verify company detail loaded for company", page=self.page, data={"company_name": company_name}):
            self.expect_detail_shell_loaded()
            self._expect_company_name_field_matches(company_name, timeout_ms=5_000)

    def expect_detail_shell_loaded(self) -> None:
        with allure_step("Verify company detail shell loaded", page=self.page):
            self.first_visible(
                [
                    ("Company Details heading", self.page.get_by_role("heading", name=re.compile(r"Company Details", re.I)).first),
                    # Text fallback is justified because this is the assignment-required profile page title.
                    ("Company Details text", self.page.get_by_text("Company Details", exact=True).first),
                    ("Profile Account tab", self.page.get_by_text("Profile Account", exact=True).first),
                ],
                "company detail shell",
                timeout_ms=10_000,
            )

    def expect_company_values(self, data: CompanyRegistrationData) -> None:
        with allure_step("Verify company detail values", page=self.page, data=data.expected_detail_values()):
            expected_values = data.expected_detail_values()
            self.refresh_until_company_name_loaded(data.company_name)
            attach_json("company-detail-expected-values", expected_values)

            # Tier 2: detail name is checked first and must match before other fields.
            self._expect_company_name_field_matches(data.company_name, timeout_ms=5_000)
            # Tier 2: detail industry type must match submitted Industry Type.
            self.expect_detail_value(self.industry_type, data.industry_type)
            # Tier 2: detail company type must match submitted Company Type.
            self.expect_detail_value(self.company_type, data.company_type)
            # Tier 2: detail address must include submitted Street Address.
            self.expect_detail_value(self.address, data.street_address)
            # Tier 2: detail postal code must match submitted Postal Code.
            self.expect_detail_value(self.postal_code, data.location.postal_code)
            # Tier 2: detail email must match submitted Email.
            self.expect_detail_value(self.email, data.email)
            # Tier 2: detail phone must match submitted Phone.
            self.expect_detail_value(self.phone, data.phone)

    def expect_detail_value(self, spec: DetailFieldSpec, expected_value: str) -> None:
        with allure_step(
            f"Verify company detail {spec.label}",
            page=self.page,
            data={"field": spec.label, "expected_value": expected_value},
        ):
            errors: list[str] = []
            for description, locator in self._detail_value_candidates(spec, expected_value):
                try:
                    self._expect_locator_has_value(locator, expected_value)
                    return
                except (AssertionError, PlaywrightError, TimeoutError) as error:
                    errors.append(f"{description}: {error}")
            raise AssertionError(
                f"Could not verify company detail {spec.label!r} value {expected_value!r}; tried {len(errors)} locators"
            )

    def company_id_value(self) -> str:
        with allure_step("Read generated Company ID", page=self.page):
            value = self._detail_field_current_value(self.company_id)
            attach_json("company-detail-id", {"company_id": value})
            return value

    def delete_current_company(self) -> None:
        with allure_step("Delete current company from detail page", page=self.page):
            self._delete_action().click()
            self._confirm_delete_if_needed()
            self._wait_after_delete()

    def _delete_action(self) -> Locator:
        return self.first_visible(
            [
                ("button named Delete", self.page.get_by_role("button", name=DELETE_ACTION).first),
                ("link named Delete", self.page.get_by_role("link", name=DELETE_ACTION).first),
                ("stable delete control", self.page.locator(stable_action_selector("delete")).first),
                # Text fallback is justified because delete is an assignment-required cleanup action.
                ("assignment-required Delete text", self.page.get_by_text("Delete", exact=True).first),
                # Text fallback is justified because eSuite may localize the cleanup action.
                ("localized Hapus text", self.page.get_by_text("Hapus", exact=True).first),
            ],
            "company delete action",
            timeout_ms=10_000,
        )

    def _confirm_delete_if_needed(self) -> None:
        with allure_step("Confirm delete company dialog", page=self.page):
            confirm_delete_if_needed(self.page)

    def _wait_after_delete(self) -> None:
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=2_000)
        except TimeoutError:
            pass

    def _detail_value_candidates(self, spec: DetailFieldSpec, expected_value: str) -> list[tuple[str, Locator]]:
        label = re.compile(re.escape(spec.label), re.I)
        exact_value = re.compile(rf"^\s*{re.escape(expected_value)}\s*$", re.I)
        candidates = [
            (f"placeholder {placeholder}", self.page.get_by_placeholder(placeholder).first)
            for placeholder in spec.placeholders
        ]
        candidates.extend(
            [
                ("combobox with exact value", self.page.get_by_role("combobox").filter(has_text=exact_value).first),
                # Text fallback is justified because eSuite profile renders select values as visible read-only text.
                ("exact visible detail text", self.page.get_by_text(expected_value, exact=True).first),
                # Text fallback is justified because long address fields may be rendered with surrounding location text.
                ("contained visible detail text", self.page.get_by_text(expected_value, exact=False).first),
            ]
        )
        candidates.extend((f"data-testid {test_id}", self.page.get_by_test_id(test_id).first) for test_id in spec.test_ids)
        candidates.extend(
            [
                (
                    f"row containing {spec.label}",
                    self.page.get_by_role("row").filter(has_text=label).filter(has_text=expected_value).first,
                ),
                ("cell with exact value", self.page.get_by_role("cell", name=exact_value).first),
                ("textbox labelled field", self.page.get_by_label(label).first),
            ]
        )
        candidates.extend(
            [
                (f"stable name/id {stable_name}", self.page.locator(stable_detail_selector(stable_name)).first)
                for stable_name in spec.stable_names
            ]
        )
        return candidates

    def _detail_field_current_value(self, spec: DetailFieldSpec) -> str:
        errors: list[str] = []
        for description, locator in self._detail_field_candidates(spec):
            try:
                expect(locator).to_be_visible(timeout=1_000)
                value = self._locator_current_value(locator)
                if _is_meaningful_detail_value(value):
                    return value
                errors.append(f"{description}: empty")
            except (AssertionError, PlaywrightError, TimeoutError) as error:
                errors.append(f"{description}: {error}")
        raise AssertionError(f"Could not read company detail {spec.label!r}; tried {len(errors)} locators")

    def _detail_field_candidates(self, spec: DetailFieldSpec) -> list[tuple[str, Locator]]:
        label = re.compile(re.escape(spec.label), re.I)
        candidates = [
            (f"placeholder {placeholder}", self.page.get_by_placeholder(placeholder).first)
            for placeholder in spec.placeholders
        ]
        candidates.extend((f"data-testid {test_id}", self.page.get_by_test_id(test_id).first) for test_id in spec.test_ids)
        candidates.extend((f"stable name/id {stable_name}", self.page.locator(stable_detail_selector(stable_name)).first) for stable_name in spec.stable_names)
        candidates.append(("textbox labelled field", self.page.get_by_label(label).first))
        return candidates

    @staticmethod
    def _expect_locator_has_value(locator: Locator, expected_value: str) -> None:
        expect(locator).to_be_visible(timeout=1_000)
        try:
            expect(locator).to_have_value(expected_value, timeout=1_000)
            return
        except (AssertionError, PlaywrightError):
            pass
        expect(locator).to_contain_text(expected_value, timeout=1_000)

    @staticmethod
    def _locator_current_value(locator: Locator) -> str:
        for getter in (locator.input_value, locator.text_content):
            try:
                value = getter(timeout=1_000)
            except (PlaywrightError, TimeoutError):
                continue
            normalized = " ".join((value or "").split())
            if normalized:
                return normalized
        return ""

    def refresh_once_if_company_name_empty(self, company_name: str) -> None:
        self.refresh_until_company_name_loaded(company_name)

    def refresh_until_company_name_loaded(self, company_name: str, max_reloads: int = DETAIL_EMPTY_MAX_RELOADS) -> None:
        with allure_step(
            "Wait for Company Name field to load",
            page=self.page,
            data={"company_name": company_name, "max_reloads": max_reloads, "wait_per_attempt_ms": DETAIL_EMPTY_REFRESH_TIMEOUT_MS},
        ):
            self.expect_detail_shell_loaded()
            for reload_attempt in range(0, max_reloads + 1):
                if self._company_name_field_ready(
                    company_name,
                    require_expected=True,
                    timeout_ms=DETAIL_EMPTY_REFRESH_TIMEOUT_MS,
                ):
                    if reload_attempt > 0:
                        attach_json(
                            "company-detail-refresh-resolved",
                            {
                                "company_name": company_name,
                                "reload_attempt": reload_attempt,
                                "max_reloads": max_reloads,
                            },
                        )
                    return

                observed_value = self._company_name_field_current_value_now()
                if observed_value:
                    if _detail_values_match(observed_value, company_name):
                        attach_json(
                            "company-detail-refresh-resolved-by-field-read",
                            {
                                "company_name": company_name,
                                "observed_value": observed_value,
                                "reload_attempt": reload_attempt,
                                "max_reloads": max_reloads,
                            },
                        )
                        return
                    raise AssertionError(
                        f"Company Name field loaded {observed_value!r}, expected {company_name!r}"
                    )

                if reload_attempt == max_reloads:
                    attach_json(
                        "company-detail-refresh-limit-reached",
                        {
                            "company_name": company_name,
                            "max_reloads": max_reloads,
                            "reason": "company_name field still empty after repeated 2 second waits",
                        },
                    )
                    raise CompanyDetailDataNotLoadedError(
                        f"Company Name field stayed empty after {max_reloads} reloads for {company_name!r}"
                    )

                with allure_step(
                    "Reload company detail because Company Name is empty",
                    page=self.page,
                    data={
                        "company_name": company_name,
                        "reload_attempt": reload_attempt + 1,
                        "max_reloads": max_reloads,
                    },
                ):
                    attach_json(
                        "company-detail-refresh",
                        {
                            "company_name": company_name,
                            "reload_attempt": reload_attempt + 1,
                            "max_reloads": max_reloads,
                            "reason": "company_name field empty for 2 seconds after opening Manage",
                        },
                    )
                    self.page.reload(wait_until="domcontentloaded")
                    self.expect_detail_shell_loaded()
            self._expect_company_name_field_matches(company_name, timeout_ms=5_000)

    def _company_name_field_has_value(self, timeout_ms: int) -> bool:
        return self._company_name_field_ready("", require_expected=False, timeout_ms=timeout_ms)

    def _company_name_field_has_value_now(self) -> bool:
        return bool(self._company_name_field_current_value_now())

    def _company_name_field_current_value_now(self) -> str:
        try:
            return str(self.page.evaluate(DETAIL_COMPANY_NAME_FIELD_VALUE_SCRIPT) or "").strip()
        except PlaywrightError:
            return ""

    def _expect_company_name_field_matches(self, company_name: str, timeout_ms: int) -> None:
        if self._company_name_field_ready(company_name, require_expected=True, timeout_ms=timeout_ms):
            return
        observed_value = self._company_name_field_current_value_now()
        if _detail_values_match(observed_value, company_name):
            return
        if observed_value:
            raise AssertionError(f"Company Name field loaded {observed_value!r}, expected {company_name!r}")
        raise AssertionError(f"Company Name field did not match {company_name!r}")

    def _company_name_field_ready(self, company_name: str, require_expected: bool, timeout_ms: int) -> bool:
        try:
            self.page.wait_for_function(
                DETAIL_COMPANY_NAME_FIELD_SCRIPT,
                arg={"expected": company_name, "requireExpected": require_expected},
                timeout=timeout_ms,
            )
            return True
        except TimeoutError:
            return False


def stable_detail_selector(stable_name: str) -> str:
    return (
        f"[name='{stable_name}'], [id='{stable_name}'], "
        f"input[aria-label='{stable_name}'], textarea[aria-label='{stable_name}'], "
        f"[aria-label='{stable_name}']"
    )


def stable_action_selector(action_name: str) -> str:
    return (
        f"button[name='{action_name}'], button[id='{action_name}'], "
        f"button[aria-label='{action_name}'], a[name='{action_name}'], "
        f"a[id='{action_name}'], a[aria-label='{action_name}']"
    )


def confirm_delete_if_needed(page: Page) -> None:
    with allure_step("Handle delete confirmation dialog", page=page):
        _accept_delete_agreement_if_present(page)
        candidates = [
            ("confirmation Confirm button", page.get_by_role("button", name=re.compile(r"^Confirm$", re.I)).first),
            ("confirmation button", page.get_by_role("button", name=CONFIRM_DELETE_ACTION).first),
            # Text fallback is justified because confirmation dialogs often lack stable roles.
            ("confirmation Delete text", page.get_by_text("Delete", exact=True).last),
            # Text fallback is justified because eSuite may localize confirmation text.
            ("confirmation Hapus text", page.get_by_text("Hapus", exact=True).last),
        ]
        for _, locator in candidates:
            try:
                expect(locator).to_be_visible(timeout=3_000)
                expect(locator).to_be_enabled(timeout=3_000)
                with allure_step("Click delete confirmation Confirm", page=page):
                    locator.click()
                _expect_delete_confirmation_closed(page)
                return
            except (AssertionError, PlaywrightError, TimeoutError):
                continue
        if _delete_confirmation_is_visible(page):
            raise AssertionError("Could not confirm company deletion; confirmation dialog is still visible")


def _accept_delete_agreement_if_present(page: Page) -> None:
    with allure_step(
        "Accept delete agreement checkbox",
        page=page,
        data={"agreement": "I understand & agree to delete"},
    ):
        candidates = [
            (
                "delete agreement row checkbox",
                page.locator("div.align-center.flex.flex-row")
                .filter(has_text=DELETE_AGREEMENT)
                .locator("button[role='checkbox']")
                .first,
            ),
            ("delete agreement stable checkbox", page.locator("button[role='checkbox']#select-all").last),
            ("delete agreement checkbox by label", page.get_by_label(DELETE_AGREEMENT).first),
            ("delete agreement checkbox role", page.get_by_role("checkbox", name=DELETE_AGREEMENT).first),
            ("visible role checkbox", page.get_by_role("checkbox").last),
            ("visible delete checkbox", page.locator("input[type='checkbox']").last),
        ]
        for _, locator in candidates:
            try:
                expect(locator).to_be_visible(timeout=1_000)
                _check_or_click(locator)
                return
            except (AssertionError, PlaywrightError, TimeoutError):
                continue
        _click_delete_agreement_box_by_text_position(page)


def _check_or_click(locator: Locator) -> None:
    try:
        if locator.is_checked(timeout=500):
            return
    except (PlaywrightError, TimeoutError):
        pass
    try:
        locator.check(timeout=1_000)
    except (PlaywrightError, TimeoutError):
        locator.click(timeout=1_000)


def _click_delete_agreement_box_by_text_position(page: Page) -> None:
    label = page.get_by_text(DELETE_AGREEMENT).first
    expect(label).to_be_visible(timeout=1_000)
    coordinates = page.evaluate(
        """
        () => {
          const pattern = /I understand\\s*&\\s*agree to delete/i;
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          let node = walker.nextNode();
          while (node) {
            if (pattern.test(node.nodeValue || "")) {
              const range = document.createRange();
              range.selectNodeContents(node);
              const rect = range.getBoundingClientRect();
              range.detach();
              if (rect.width > 0 && rect.height > 0) {
                const offset = Math.max(18, Math.min(28, rect.height * 1.2));
                return { x: Math.max(1, rect.left - offset), y: rect.top + rect.height / 2 };
              }
            }
            node = walker.nextNode();
          }
          return null;
        }
        """
    )
    if not coordinates:
        box = label.bounding_box()
        if not box:
            raise AssertionError("Delete agreement checkbox label has no visible box")
        coordinates = {"x": box["x"] + 10, "y": box["y"] + (box["height"] / 2)}
    page.mouse.click(coordinates["x"], coordinates["y"])


def _expect_delete_confirmation_closed(page: Page) -> None:
    if not _delete_confirmation_is_visible(page):
        return
    try:
        expect(page.get_by_text("Confirmation Delete", exact=True).first).not_to_be_visible(timeout=5_000)
    except AssertionError as error:
        raise AssertionError("Delete confirmation stayed open after Confirm; delete agreement checkbox was not accepted") from error


def _delete_confirmation_is_visible(page: Page) -> bool:
    try:
        expect(page.get_by_text("Confirmation Delete", exact=True).first).to_be_visible(timeout=500)
        return True
    except (AssertionError, PlaywrightError, TimeoutError):
        return False


def _is_meaningful_detail_value(value: str) -> bool:
    lowered = value.strip().lower()
    return bool(lowered) and not lowered.startswith(("input ", "choose ", "select "))


def _detail_values_match(actual_value: str, expected_value: str) -> bool:
    actual = " ".join(actual_value.split()).casefold()
    expected = " ".join(expected_value.split()).casefold()
    return bool(actual and expected) and (actual == expected or expected in actual)
