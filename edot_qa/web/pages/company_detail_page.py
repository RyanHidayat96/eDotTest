from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, TimeoutError, expect

from edot_qa.reporting.allure_helpers import attach_json
from edot_qa.web.base_page import BasePage
from edot_qa.web.company_registration import CompanyRegistrationData


DELETE_ACTION = re.compile(r"^(Delete|Hapus|Remove)$", re.I)
CONFIRM_DELETE_ACTION = re.compile(r"^(Confirm|Delete|Hapus|Yes|Ya|OK)$", re.I)
DELETE_AGREEMENT = re.compile(r"I understand\s*&\s*agree to delete", re.I)
DETAIL_EMPTY_REFRESH_TIMEOUT_MS = 2_000
DETAIL_VALUE_READY_SCRIPT = """
(values) => {
  const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
  const compact = (value) => normalize(value).replace(/[^a-z0-9]+/g, "");
  const expected = values
    .map((value) => ({ normalized: normalize(value), compacted: compact(value) }))
    .filter((value) => value.normalized || value.compacted);
  const visible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const elements = Array.from(
    document.querySelectorAll(
      "input, textarea, select, button, [role='combobox'], [role='textbox'], [data-testid], [aria-label], p, span, div"
    )
  );
  return expected.some((needle) =>
    elements.some((element) => {
      if (!visible(element)) return false;
      const valuesToCheck = [
        element.value,
        element.textContent,
        element.getAttribute("aria-label"),
        element.getAttribute("title"),
      ];
      return valuesToCheck.some((candidate) => {
        const normalizedCandidate = normalize(candidate);
        const compactedCandidate = compact(candidate);
        return (
          (needle.normalized && normalizedCandidate.includes(needle.normalized)) ||
          (needle.compacted && compactedCandidate.includes(needle.compacted))
        );
      });
    })
  );
}
"""


@dataclass(frozen=True)
class DetailFieldSpec:
    label: str
    test_ids: tuple[str, ...]
    stable_names: tuple[str, ...]
    placeholders: tuple[str, ...] = ()


class CompanyDetailPage(BasePage):
    name = DetailFieldSpec(
        "name",
        ("company-name", "companyName"),
        ("companyName", "company_name", "name"),
        ("Input Company Name",),
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
        expect(self.page.get_by_text(company_name, exact=True).first).to_be_visible(timeout=20_000)

    def expect_company_values(self, data: CompanyRegistrationData) -> None:
        expected_values = data.expected_detail_values()
        self._refresh_once_if_detail_values_empty(data.company_name, expected_values)
        attach_json("company-detail-expected-values", expected_values)

        # Tier 2: detail name must match submitted Company Name.
        self.expect_detail_value(self.name, data.company_name)
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

    def delete_current_company(self) -> None:
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

    @staticmethod
    def _expect_locator_has_value(locator: Locator, expected_value: str) -> None:
        expect(locator).to_be_visible(timeout=1_000)
        try:
            expect(locator).to_have_value(expected_value, timeout=1_000)
            return
        except (AssertionError, PlaywrightError):
            pass
        expect(locator).to_contain_text(expected_value, timeout=1_000)

    def _refresh_once_if_detail_values_empty(self, company_name: str, expected_values: dict[str, str]) -> None:
        values_to_probe = [value for label, value in expected_values.items() if label != "name"]
        if self._has_any_expected_detail_value(values_to_probe, timeout_ms=DETAIL_EMPTY_REFRESH_TIMEOUT_MS):
            return

        attach_json(
            "company-detail-refresh",
            {
                "company_name": company_name,
                "reason": "detail values empty for 2 seconds after opening Manage",
            },
        )
        self.page.reload(wait_until="domcontentloaded")
        self.expect_loaded_for(company_name)
        if not self._has_any_expected_detail_value(values_to_probe, timeout_ms=DETAIL_EMPTY_REFRESH_TIMEOUT_MS):
            raise AssertionError("Company detail values stayed empty for 2 seconds after refresh")

    def _has_any_expected_detail_value(self, values: list[str], timeout_ms: int) -> bool:
        try:
            self.page.wait_for_function(DETAIL_VALUE_READY_SCRIPT, arg=values, timeout=timeout_ms)
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
            locator.click()
            _expect_delete_confirmation_closed(page)
            return
        except (AssertionError, PlaywrightError, TimeoutError):
            continue
    if _delete_confirmation_is_visible(page):
        raise AssertionError("Could not confirm company deletion; confirmation dialog is still visible")


def _accept_delete_agreement_if_present(page: Page) -> None:
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
