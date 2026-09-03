from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, TimeoutError, expect

from edot_qa.web.base_page import BasePage
from edot_qa.web.company_registration import CompanyRegistrationData


@dataclass(frozen=True)
class FieldSpec:
    label: str
    test_ids: tuple[str, ...]
    stable_names: tuple[str, ...]


REGISTER_COMPANY_HEADING = re.compile(r"Register Company", re.I)
NEXT_ACTION = re.compile(r"^(Next|Lanjut)$", re.I)
SUBMIT_ACTION = re.compile(r"^(Submit|Register|Finish|Create Company|Save|Simpan)$", re.I)


class RegisterCompanyWizardPage(BasePage):
    company_name = FieldSpec("Company Name", ("company-name", "companyName"), ("companyName", "company_name"))
    email = FieldSpec("Email", ("company-email", "email"), ("email",))
    phone = FieldSpec("Phone", ("company-phone", "phone"), ("phone", "phoneNumber", "phone_number"))
    industry_type = FieldSpec(
        "Industry Type",
        ("industry-type", "industryType"),
        ("industryType", "industry_type", "industry"),
    )
    company_type = FieldSpec(
        "Company Type",
        ("company-type", "companyType"),
        ("companyType", "company_type", "type"),
    )
    language = FieldSpec("Language", ("language",), ("language", "lang"))
    street_address = FieldSpec(
        "Street Address",
        ("street-address", "streetAddress"),
        ("streetAddress", "street_address", "address"),
    )
    country = FieldSpec("Country", ("country",), ("country",))
    province = FieldSpec("Province", ("province",), ("province", "state"))
    city = FieldSpec("City", ("city",), ("city",))
    district = FieldSpec("District", ("district",), ("district",))
    zone = FieldSpec("Zone", ("zone",), ("zone",))
    postal_code = FieldSpec("Postal Code", ("postal-code", "postalCode"), ("postalCode", "postal_code", "zip"))

    @property
    def heading(self) -> Locator:
        return self.first_visible(
            [
                ("heading named Register Company", self.page.get_by_role("heading", name=REGISTER_COMPANY_HEADING).first),
                # Text fallback is justified because the assignment names this exact wizard.
                ("assignment-required Register Company text", self.page.get_by_text("Register Company", exact=False).first),
            ],
            "Register Company wizard",
            timeout_ms=15_000,
        )

    @property
    def next_button(self) -> Locator:
        return self.first_visible(
            [
                ("button named Next", self.page.get_by_role("button", name=NEXT_ACTION).first),
                # Text fallback is justified because the assignment requires this wizard action.
                ("assignment-required Next text", self.page.get_by_text("Next", exact=True).first),
            ],
            "Next action",
            timeout_ms=10_000,
        )

    @property
    def submit_button(self) -> Locator:
        return self.first_visible(
            [
                ("final wizard submit button", self.page.get_by_role("button", name=SUBMIT_ACTION).first),
                ("stable submit button", self.page.locator("button[type='submit']").first),
            ],
            "company registration submit action",
            timeout_ms=10_000,
        )

    def expect_open(self) -> None:
        expect(self.heading).to_be_visible()

    def expect_next_disabled(self) -> None:
        expect(self.next_button).to_be_disabled(timeout=10_000)

    def expect_next_enabled(self) -> None:
        expect(self.next_button).to_be_enabled(timeout=10_000)

    def expect_next_disabled_until_step_one_valid(self, data: CompanyRegistrationData) -> None:
        self.expect_next_disabled()
        self.fill_required_step_one(data)
        self.expect_next_enabled()

    def fill_required_step_one(self, data: CompanyRegistrationData) -> None:
        self.fill_text_field(self.company_name, data.company_name)
        self.fill_text_field(self.email, data.email)
        self.fill_text_field(self.phone, data.phone)
        self.choose_field_option(self.industry_type, data.industry_type)
        self.choose_field_option(self.company_type, data.company_type)
        self.choose_field_option(self.language, data.language)
        self.fill_text_field(self.street_address, data.street_address)
        self.choose_field_option(self.country, data.location.country)
        self.choose_field_option(self.province, data.location.province)
        self.choose_field_option(self.city, data.location.city)
        self.choose_field_option(self.district, data.location.district)
        self.choose_field_option(self.zone, data.location.zone)
        self.choose_or_fill_field(self.postal_code, data.location.postal_code)

    def complete_three_step_registration(self, data: CompanyRegistrationData) -> None:
        self.expect_next_disabled_until_step_one_valid(data)
        self.next_button.click()
        self.assert_step_can_continue(step_name="Register Company step 2")
        self.next_button.click()
        self.assert_step_can_continue(step_name="Register Company step 3")
        self.submit_button.click()

    def expect_created_company_visible(self, company_name: str) -> None:
        expect(self.page.get_by_text(company_name, exact=True).first).to_be_visible(timeout=30_000)

    def assert_step_can_continue(self, step_name: str) -> None:
        try:
            expect(self.next_button).to_be_enabled(timeout=10_000)
            return
        except AssertionError as error:
            raise AssertionError(
                f"{step_name} has disabled Next. Product-required fields must be discovered and filled before submission."
            ) from error

    def fill_text_field(self, spec: FieldSpec, value: str) -> None:
        control = self._text_control(spec)
        control.fill(value)
        self._expect_text_value(control, value, spec.label)

    def choose_or_fill_field(self, spec: FieldSpec, value: str) -> None:
        try:
            self.choose_field_option(spec, value)
        except AssertionError as choice_error:
            try:
                self.fill_text_field(spec, value)
            except AssertionError as fill_error:
                raise AssertionError(
                    f"Could not choose or fill {spec.label}. Choice error: {choice_error}. Fill error: {fill_error}"
                ) from fill_error

    def choose_field_option(self, spec: FieldSpec, value: str) -> None:
        errors: list[str] = []
        for description, control in self._choice_controls(spec):
            try:
                expect(control).to_be_visible(timeout=3_000)
                if self._try_native_select(control, value):
                    self._after_selection()
                    return
                control.click()
                self._visible_option(value).click()
                self._after_selection()
                return
            except (AssertionError, TimeoutError) as error:
                errors.append(f"{description}: {error}")
        raise AssertionError(f"Could not choose {value!r} for {spec.label}; tried {len(errors)} controls")

    def _text_control(self, spec: FieldSpec) -> Locator:
        label_regex = re.compile(re.escape(spec.label), re.I)
        candidates = [
            (f"data-testid {test_id}", self.page.get_by_test_id(test_id).first)
            for test_id in spec.test_ids
        ]
        candidates.extend(
            [
                (f"placeholder {spec.label}", self.page.get_by_placeholder(label_regex).first),
                (f"placeholder Input {spec.label}", self.page.get_by_placeholder(re.compile(rf"Input\s+{re.escape(spec.label)}", re.I)).first),
                (f"placeholder Input {spec.label.removeprefix('Street ')}", self.page.get_by_placeholder(re.compile(rf"Input\s+{re.escape(spec.label.removeprefix('Street '))}", re.I)).first),
                (f"label {spec.label}", self.page.get_by_label(label_regex).first),
            ]
        )
        candidates.extend(
            [
                (f"stable name/id {stable_name}", self.page.locator(stable_text_selector(stable_name)).first)
                for stable_name in spec.stable_names
            ]
        )
        candidates.append((f"textbox named {spec.label}", self.page.get_by_role("textbox", name=label_regex).first))
        return self.first_visible(candidates, f"{spec.label} input", timeout_ms=5_000)

    def _choice_controls(self, spec: FieldSpec) -> list[tuple[str, Locator]]:
        label_regex = re.compile(re.escape(spec.label), re.I)
        candidates = [
            (f"data-testid {test_id}", self.page.get_by_test_id(test_id).first)
            for test_id in spec.test_ids
        ]
        candidates.extend(
            [
                (f"combobox named {spec.label}", self.page.get_by_role("combobox", name=label_regex).first),
                (f"button named {spec.label}", self.page.get_by_role("button", name=label_regex).first),
                (f"label {spec.label}", self.page.get_by_label(label_regex).first),
            ]
        )
        candidates.extend(
            [
                (f"stable name/id {stable_name}", self.page.locator(stable_choice_selector(stable_name)).first)
                for stable_name in spec.stable_names
            ]
        )
        # Text fallback is justified because current eSuite dropdown buttons expose visible text but no stable name/id.
        candidates.append((f"assignment dropdown Choose {spec.label}", self.page.get_by_text(f"Choose {spec.label}", exact=True).first))
        return candidates

    def _visible_option(self, value: str) -> Locator:
        exact = re.compile(rf"^{re.escape(value)}$", re.I)
        return self.first_visible(
            [
                ("option with exact value", self.page.get_by_role("option", name=exact).first),
                ("menu item with exact value", self.page.get_by_role("menuitem", name=exact).first),
                # Text fallback is justified because dropdown option markup often lacks ARIA roles.
                ("visible option text", self.page.get_by_text(value, exact=True).last),
            ],
            f"option {value}",
            timeout_ms=10_000,
        )

    def _try_native_select(self, control: Locator, value: str) -> bool:
        try:
            tag_name = control.evaluate("element => element.tagName.toLowerCase()")
        except PlaywrightError:
            return False
        if tag_name != "select":
            return False
        for option_kwargs in ({"label": value}, {"value": value}):
            try:
                control.select_option(**option_kwargs)
                return True
            except PlaywrightError:
                continue
        return False

    def _after_selection(self) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=10_000)
        except TimeoutError:
            self.page.wait_for_load_state("domcontentloaded")

    @staticmethod
    def _expect_text_value(control: Locator, value: str, label: str) -> None:
        try:
            expect(control).to_have_value(value, timeout=5_000)
        except AssertionError:
            # Some custom controls expose text content rather than input value.
            expect(control).to_contain_text(value, timeout=5_000)


def stable_text_selector(stable_name: str) -> str:
    return (
        f"input[name='{stable_name}'], textarea[name='{stable_name}'], "
        f"input[id='{stable_name}'], textarea[id='{stable_name}'], "
        f"[aria-label='{stable_name}']"
    )


def stable_choice_selector(stable_name: str) -> str:
    return (
        f"select[name='{stable_name}'], [role='combobox'][name='{stable_name}'], "
        f"select[id='{stable_name}'], [id='{stable_name}'], [aria-label='{stable_name}']"
    )
