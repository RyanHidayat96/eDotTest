from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, TimeoutError, expect

from edot_qa.reporting.allure_helpers import attach_json
from edot_qa.web.base_page import BasePage
from edot_qa.web.company_registration import CompanyRegistrationData


DELETE_ACTION = re.compile(r"^(Delete|Hapus|Remove)$", re.I)
CONFIRM_DELETE_ACTION = re.compile(r"^(Delete|Hapus|Yes|Ya|Confirm|OK)$", re.I)


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
        attach_json("company-detail-expected-values", data.expected_detail_values())

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
        candidates = [
            ("confirmation button", self.page.get_by_role("button", name=CONFIRM_DELETE_ACTION).first),
            # Text fallback is justified because confirmation dialogs often lack stable roles.
            ("confirmation Delete text", self.page.get_by_text("Delete", exact=True).last),
            # Text fallback is justified because eSuite may localize confirmation text.
            ("confirmation Hapus text", self.page.get_by_text("Hapus", exact=True).last),
        ]
        for _, locator in candidates:
            try:
                expect(locator).to_be_visible(timeout=3_000)
                locator.click()
                return
            except (AssertionError, PlaywrightError, TimeoutError):
                continue

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
