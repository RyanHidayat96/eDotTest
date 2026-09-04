from __future__ import annotations

import re
import os
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, TimeoutError, expect

from edot_qa.reporting.allure_helpers import allure_step, attach_page_evidence
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
SUBMIT_SUCCESS_TEXT = re.compile(
    r"(success|successfully|created successfully|registered successfully|berhasil|sukses)",
    re.I,
)


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
    zone = FieldSpec("Sub District", ("zone", "sub-district", "subDistrict"), ("zone", "subDistrict", "sub_district"))
    postal_code = FieldSpec("Postal Code", ("postal-code", "postalCode"), ("postalCode", "postal_code", "zip"))
    branch_name = FieldSpec("Branch Name", ("branch-name", "branchName"), ("branchName", "branch_name"))

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
        with allure_step("Verify Register Company wizard is open", page=self.page):
            expect(self.heading).to_be_visible()

    def expect_next_disabled(self) -> None:
        with allure_step("Verify Next button disabled", page=self.page):
            expect(self.next_button).to_be_disabled(timeout=10_000)

    def expect_next_enabled(self) -> None:
        with allure_step("Verify Next button enabled", page=self.page):
            expect(self.next_button).to_be_enabled(timeout=10_000)

    def expect_next_disabled_until_step_one_valid(self, data: CompanyRegistrationData) -> None:
        with allure_step(
            "Validate Register Company step 1 required fields",
            page=self.page,
            data=data.as_allure_payload(),
        ):
            self.expect_next_disabled()
            self.fill_required_step_one(data, validate_dependents_after_country=True)
            self.expect_next_enabled()

    def fill_required_step_one(self, data: CompanyRegistrationData, *, validate_dependents_after_country: bool = False) -> None:
        with allure_step("Fill Register Company step 1 fields", page=self.page, data=data.as_allure_payload()):
            self.fill_text_field(self.company_name, data.company_name)
            self.fill_text_field(self.email, data.email)
            self.fill_text_field(self.phone, data.phone)
            self.choose_field_option(self.industry_type, data.industry_type)
            self.choose_field_option(self.company_type, data.company_type)
            self.choose_field_option(self.language, data.language)
            self.fill_text_field(self.street_address, data.street_address)
            self.choose_field_option(self.country, data.location.country)
            if validate_dependents_after_country:
                self.expect_location_dependents_disabled_after_country_only()
            self.choose_field_option(self.province, data.location.province)
            self.choose_field_option(self.city, data.location.city)
            self.choose_field_option(self.district, data.location.district)
            self.choose_field_option(self.zone, data.location.zone)
            self.choose_or_fill_field(self.postal_code, data.location.postal_code)

    def expect_location_dependents_disabled_after_country_only(self) -> None:
        with allure_step("Verify dependent location fields stay disabled after Country only", page=self.page):
            for spec, placeholder in (
                (self.city, "Choose City"),
                (self.district, "Choose District"),
                (self.zone, "Choose Sub District"),
                (self.postal_code, "Choose Postal Code"),
            ):
                if self._visible_control_is_disabled(placeholder):
                    continue
                control = self._choice_control_by_visible_text(spec, placeholder)
                self._expect_required_control_disabled(control, spec)

    def complete_three_step_registration(self, data: CompanyRegistrationData) -> None:
        with allure_step("Complete Register Company three step wizard", page=self.page):
            with allure_step("Register Company page 1 - Company details", page=self.page, screenshot=True, force=True):
                self.expect_next_disabled_until_step_one_valid(data)
            with allure_step("Register Company page 2 - Company settings", page=self.page, screenshot=True, force=True):
                self.next_button.click()
                self.assert_step_can_continue(step_name="Register Company step 2")
            with allure_step("Register Company page 3 - Branch details", page=self.page, screenshot=True, force=True):
                self.next_button.click()
                self.fill_required_step_three(data)
                self.expect_submit_enabled()
            with allure_step(
                "Submit Register Company wizard",
                page=self.page,
                data={"company_name": data.company_name},
                screenshot=False,
                force=True,
            ):
                self.submit_button.click()
                self._wait_for_submit_success(data.company_name)
                attach_page_evidence("Submit success", self.page, screenshot=True)

    def expect_created_company_visible(self, company_name: str) -> None:
        with allure_step(
            "Verify created company is visible after submit",
            page=self.page,
            data={"company_name": company_name},
        ):
            expect(self.page.get_by_text(company_name, exact=True).first).to_be_visible(timeout=30_000)

    def _wait_for_submit_success(self, company_name: str) -> None:
        if self._success_notification_visible(timeout_ms=15_000):
            return
        try:
            self.page.wait_for_url(
                lambda url: "/companies" in url and "registration-companies" not in url,
                timeout=10_000,
            )
            self.page.wait_for_load_state("domcontentloaded")
            return
        except TimeoutError:
            pass
        try:
            expect(self.page.get_by_text(company_name, exact=True).first).to_be_visible(timeout=10_000)
        except AssertionError as error:
            raise AssertionError(
                f"Company registration submit did not show a success notification or created company {company_name!r}."
            ) from error

    def _success_notification_visible(self, timeout_ms: int) -> bool:
        candidates = [
            self.page.get_by_role("alert").filter(has_text=SUBMIT_SUCCESS_TEXT).first,
            self.page.get_by_role("status").filter(has_text=SUBMIT_SUCCESS_TEXT).first,
            self.page.locator(
                "[data-sonner-toast], [role='alert'], [role='status'], "
                "[class*='toast' i], [class*='notification' i], [class*='alert' i]"
            ).filter(has_text=SUBMIT_SUCCESS_TEXT).first,
            # Text fallback is justified because eSuite success toasts may lack stable roles/classes.
            self.page.get_by_text(SUBMIT_SUCCESS_TEXT).first,
        ]
        timeout_per_candidate = max(1_000, timeout_ms // len(candidates))
        for locator in candidates:
            try:
                expect(locator).to_be_visible(timeout=timeout_per_candidate)
                return True
            except (AssertionError, TimeoutError, PlaywrightError):
                continue
        return False

    def assert_step_can_continue(self, step_name: str) -> None:
        with allure_step(f"Verify {step_name} can continue", page=self.page):
            try:
                expect(self.next_button).to_be_enabled(timeout=10_000)
                return
            except AssertionError as error:
                raise AssertionError(
                    f"{step_name} has disabled Next. Product-required fields must be discovered and filled before submission."
                ) from error

    def fill_required_step_three(self, data: CompanyRegistrationData) -> None:
        with allure_step(
            "Fill Register Company step 3 branch fields",
            page=self.page,
            data={"branch_name": data.branch_name, "company_name": data.company_name},
        ):
            self.fill_text_field(self.branch_name, data.branch_name)
            if not self._try_fill_branch_from_company_records():
                self.fill_text_field(self.street_address, data.street_address)
                self.choose_field_option(self.country, data.location.country)
                self.choose_field_option(self.province, data.location.province)
                self.choose_field_option(self.city, data.location.city)
                self.choose_field_option(self.district, data.location.district)
                self.choose_field_option(self.zone, data.location.zone)
                self.choose_or_fill_field(self.postal_code, data.location.postal_code)
            self.accept_terms()

    def expect_submit_enabled(self) -> None:
        with allure_step("Verify Submit button enabled", page=self.page):
            expect(self.submit_button).to_be_enabled(timeout=10_000)

    def accept_terms(self) -> None:
        with allure_step(
            "Accept Register Company terms",
            page=self.page,
            input_data={"field": "Terms and Conditions", "value": "accepted"},
        ):
            checkbox = self.first_visible(
                [
                    ("terms checkbox role", self.page.get_by_role("checkbox").first),
                    ("stable terms checkbox", self.page.locator("input[type='checkbox']").first),
                ],
                "terms and conditions checkbox",
                timeout_ms=10_000,
            )
            if not checkbox.is_checked():
                checkbox.check()

    def _try_fill_branch_from_company_records(self) -> bool:
        with allure_step("Try copy branch data from company records", page=self.page):
            button = self.page.get_by_role(
                "button",
                # Text fallback in accessible name is justified because eSuite exposes this exact branch-copy action.
                name=re.compile(r"Fill in with the same data from the Company records", re.I),
            ).first
            try:
                expect(button).to_be_visible(timeout=5_000)
                button.click()
                self._after_selection()
                return True
            except (AssertionError, TimeoutError, PlaywrightError):
                return False

    def fill_text_field(self, spec: FieldSpec, value: str) -> None:
        with allure_step(
            f"Input {spec.label}",
            page=self.page,
            input_data={"field": spec.label, "value": value},
        ):
            if spec.label == "Street Address":
                _console_debug("street address: try direct DOM fill")
                if self._try_fill_street_address(value):
                    _console_debug("street address: direct DOM fill pass")
                    return
                _console_debug("street address: direct DOM fill fallback to locator")
            _console_debug(f"{spec.label}: resolving input")
            control = self._text_control(spec)
            _console_debug(f"{spec.label}: input resolved")
            self._assert_required_control_editable(control, spec)
            _console_debug(f"{spec.label}: fill")
            control.fill(value, timeout=2_000)
            _console_debug(f"{spec.label}: verify value")
            self._expect_text_value(control, value, spec.label)
            _console_debug(f"{spec.label}: pass")

    def choose_or_fill_field(self, spec: FieldSpec, value: str) -> None:
        with allure_step(
            f"Choose or input {spec.label}",
            page=self.page,
        ):
            if spec.label == "Postal Code":
                if self._field_value_is_visible(value):
                    return
            try:
                self.choose_field_option(spec, value)
            except AssertionError as choice_error:
                try:
                    self.fill_text_field(spec, value)
                except AssertionError as fill_error:
                    if spec.label == "Postal Code" and self._field_value_is_visible(value):
                        return
                    raise AssertionError(
                        f"Could not choose or fill {spec.label}. Choice error: {choice_error}. Fill error: {fill_error}"
                    ) from fill_error

    def choose_field_option(self, spec: FieldSpec, value: str) -> None:
        with allure_step(
            f"Choose {spec.label}",
            page=self.page,
            input_data={"field": spec.label, "value": value},
        ):
            errors: list[str] = []
            for description, control in self._choice_controls(spec):
                try:
                    expect(control).to_be_visible(timeout=1_000)
                    self._assert_required_control_editable(control, spec)
                    if self._try_native_select(control, value):
                        self._after_selection()
                        return
                    control.click()
                    if (
                        self._try_click_visible_option(value, timeout_ms=750)
                        or self._try_filter_and_click_option(value)
                        or self._try_click_visible_option(value, timeout_ms=3_000)
                    ):
                        self._after_selection()
                        return
                except (AssertionError, TimeoutError, PlaywrightError) as error:
                    errors.append(f"{description}: {error}")
            raise AssertionError(f"Could not choose {value!r} for {spec.label}; tried {len(errors)} controls")

    def _text_control(self, spec: FieldSpec) -> Locator:
        if spec.label == "Street Address":
            return self.first_visible(
                [
                    ("street address label-adjacent input", self._input_after_label("Street Address")),
                    (
                        "street address visible placeholder",
                        self.page.locator(
                            "input[placeholder='Input Address']:visible, textarea[placeholder='Input Address']:visible, "
                            "input[placeholder*='Address']:visible, textarea[placeholder*='Address']:visible"
                        ).first,
                    ),
                ],
                f"{spec.label} input",
                timeout_ms=1_000,
            )

        label_regex = re.compile(re.escape(spec.label), re.I)
        candidates = existing_locator_candidates(
            [
                (f"data-testid {test_id}", self.page.get_by_test_id(test_id).first)
                for test_id in spec.test_ids
            ]
        )
        candidates.extend(
            [
                (f"placeholder Input {spec.label.removeprefix('Street ')}", self.page.get_by_placeholder(re.compile(rf"Input\s+{re.escape(spec.label.removeprefix('Street '))}", re.I)).first),
                (f"placeholder {spec.label}", self.page.get_by_placeholder(label_regex).first),
                (f"placeholder Input {spec.label}", self.page.get_by_placeholder(re.compile(rf"Input\s+{re.escape(spec.label)}", re.I)).first),
                (f"label {spec.label}", self.page.get_by_label(label_regex).first),
            ]
        )
        candidates.extend(
            existing_locator_candidates(
                [
                (f"stable name/id {stable_name}", self.page.locator(stable_text_selector(stable_name)).first)
                for stable_name in spec.stable_names
                ]
            )
        )
        candidates.append((f"textbox named {spec.label}", self.page.get_by_role("textbox", name=label_regex).first))
        return self.first_visible(candidates, f"{spec.label} input", timeout_ms=1_500)

    def _input_after_label(self, label: str) -> Locator:
        return self.page.locator(
            "xpath=("
            f"//*[self::label or self::div or self::span][contains(normalize-space(.), '{label}') "
            "and string-length(normalize-space(.)) <= 40]"
            "/following::*[self::input or self::textarea][(not(@type) or @type!='hidden') "
            "and not(ancestor-or-self::*[contains(@style, 'display: none')])][1]"
            ")[1]"
        )

    def _choice_controls(self, spec: FieldSpec) -> list[tuple[str, Locator]]:
        label_regex = re.compile(re.escape(spec.label), re.I)
        candidates = existing_locator_candidates(
            [
                (f"data-testid {test_id}", self.page.get_by_test_id(test_id).first)
                for test_id in spec.test_ids
            ]
        )
        candidates.extend(
            existing_locator_candidates(
                [
                (f"combobox containing Choose {spec.label}", self.page.get_by_role("combobox").filter(has_text=f"Choose {spec.label}").first),
                (f"button containing Choose {spec.label}", self.page.get_by_role("button").filter(has_text=f"Choose {spec.label}").first),
                (f"combobox named {spec.label}", self.page.get_by_role("combobox", name=label_regex).first),
                (f"button named {spec.label}", self.page.get_by_role("button", name=label_regex).first),
                (f"label {spec.label}", self.page.get_by_label(label_regex).first),
                ]
            )
        )
        candidates.extend(
            existing_locator_candidates(
                [
                (f"stable name/id {stable_name}", self.page.locator(stable_choice_selector(stable_name)).first)
                for stable_name in spec.stable_names
                ]
            )
        )
        # Text fallback is justified because current eSuite dropdown buttons expose visible text but no stable name/id.
        candidates.append((f"assignment dropdown Choose {spec.label}", self.page.get_by_text(f"Choose {spec.label}", exact=True).first))
        return candidates

    def _choice_control_by_visible_text(self, spec: FieldSpec, text: str) -> Locator:
        return self.first_visible(
            [
                # Text fallback is justified because eSuite cascade controls expose selected placeholder text.
                (f"visible {spec.label} placeholder", self.page.get_by_text(text, exact=True).first),
                ("button containing visible choice text", self.page.get_by_role("button").filter(has_text=text).first),
                ("combobox containing visible choice text", self.page.get_by_role("combobox").filter(has_text=text).first),
            ],
            f"{spec.label} disabled cascade control",
            timeout_ms=1_000,
        )

    def _visible_option(self, value: str, *, timeout_ms: int = 10_000) -> Locator:
        exact = re.compile(rf"^{re.escape(value)}$", re.I)
        role_candidates = existing_locator_candidates(
            [
                ("option with exact value", self.page.get_by_role("option", name=exact).first),
                ("menu item with exact value", self.page.get_by_role("menuitem", name=exact).first),
            ]
        )
        return self.first_visible(
            role_candidates
            + [
                # Text fallback is justified because dropdown option markup often lacks ARIA roles.
                ("visible option text regex", self.page.get_by_text(exact).last),
            ],
            f"option {value}",
            timeout_ms=timeout_ms,
        )

    def _try_click_visible_option(self, value: str, *, timeout_ms: int = 10_000) -> bool:
        try:
            self._visible_option(value, timeout_ms=timeout_ms).click()
            return True
        except (AssertionError, TimeoutError, PlaywrightError):
            return False

    def _try_filter_and_click_option(self, value: str) -> bool:
        search_regex = re.compile(r"^Search$", re.I)
        search_controls = [
            ("dropdown search input", self.page.locator("input[placeholder='Search']").last),
            ("dropdown searchbox", self.page.get_by_role("searchbox").last),
            ("dropdown search placeholder", self.page.get_by_placeholder(search_regex).last),
        ]
        for _, search_control in search_controls:
            try:
                expect(search_control).to_be_visible(timeout=500)
                search_control.fill(value, timeout=1_000)
                return self._try_click_visible_option(value, timeout_ms=2_000)
            except (AssertionError, TimeoutError, PlaywrightError):
                continue
        return False

    def _field_value_is_visible(self, value: str) -> bool:
        exact_value = re.compile(rf"^\s*{re.escape(value)}\s*$", re.I)
        try:
            # Text fallback is justified because some eSuite cascade fields render selected read-only values as plain text.
            expect(self.page.get_by_text(exact_value).last).to_be_visible(timeout=3_000)
            return True
        except (AssertionError, TimeoutError, PlaywrightError):
            return False

    def _try_fill_street_address(self, value: str) -> bool:
        try:
            _console_debug("street address: page.evaluate start")
            result: Any = self.page.evaluate(
                """value => {
                    const isVisible = element => Boolean(
                        element.offsetWidth || element.offsetHeight || element.getClientRects().length
                    );
                    const isEditable = element => !element.disabled
                        && !element.readOnly
                        && element.getAttribute('aria-disabled') !== 'true';
                    const controls = Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea'))
                        .filter(element => isVisible(element) && isEditable(element));
                    const labels = Array.from(document.querySelectorAll('label, div, span'))
                        .filter(element => {
                            const text = (element.textContent || '').trim();
                            return text.includes('Street Address') && text.length <= 40 && isVisible(element);
                        });
                    const byLabel = labels
                        .map(label => controls.find(control => Boolean(
                            label.compareDocumentPosition(control) & Node.DOCUMENT_POSITION_FOLLOWING
                        )))
                        .find(Boolean);
                    const control = byLabel || controls.find(element => {
                        const placeholder = element.getAttribute('placeholder') || '';
                        return placeholder.toLowerCase().includes('address');
                    });
                    if (!control) return {ok: false, reason: 'street address input not found'};
                    control.scrollIntoView({block: 'center', inline: 'nearest'});
                    control.focus();
                    const prototype = control.tagName.toLowerCase() === 'textarea'
                        ? HTMLTextAreaElement.prototype
                        : HTMLInputElement.prototype;
                    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
                    if (descriptor && descriptor.set) {
                        descriptor.set.call(control, value);
                    } else {
                        control.value = value;
                    }
                    control.dispatchEvent(new Event('input', {bubbles: true}));
                    control.dispatchEvent(new Event('change', {bubbles: true}));
                    control.blur();
                    return {
                        ok: control.value === value,
                        value: control.value,
                        placeholder: control.getAttribute('placeholder') || '',
                    };
                }""",
                value,
            )
        except PlaywrightError:
            return False
        _console_debug(f"street address: page.evaluate result={result}")
        return isinstance(result, dict) and result.get("ok") is True

    def _visible_control_is_disabled(self, text: str) -> bool:
        try:
            return bool(
                self.page.evaluate(
                    """text => {
                        const controls = Array.from(
                            document.querySelectorAll('button,input,textarea,select,[role="combobox"]')
                        );
                        return controls.some(element => {
                            const visible = Boolean(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
                            if (!visible) return false;
                            const value = element.value || element.innerText || element.textContent || element.getAttribute('placeholder') || '';
                            if (!value.toLowerCase().includes(text.toLowerCase())) return false;
                            return Boolean(element.disabled)
                                || element.readOnly === true
                                || element.getAttribute('aria-disabled') === 'true';
                        });
                    }""",
                    text,
                )
            )
        except PlaywrightError:
            return False

    def _assert_required_control_editable(self, control: Locator, spec: FieldSpec) -> None:
        try:
            expect(control).to_be_enabled(timeout=1_000)
            readonly = control.evaluate(
                """element => {
                    const control = element.closest('input,textarea,select,button,[role="combobox"],[aria-disabled]');
                    if (!control) return false;
                    return Boolean(control.readOnly)
                        || Boolean(control.disabled)
                        || control.getAttribute('aria-disabled') === 'true';
                }"""
            )
            if not readonly:
                return
        except (AssertionError, TimeoutError, PlaywrightError):
            pass
        raise AssertionError(
            f"Product bug candidate: mandatory field {spec.label!r} is disabled or read-only when automation must enter/choose a value."
        )

    def _expect_required_control_disabled(self, control: Locator, spec: FieldSpec) -> None:
        try:
            expect(control).to_be_disabled(timeout=1_000)
            return
        except (AssertionError, TimeoutError, PlaywrightError):
            pass
        try:
            disabled = control.evaluate(
                """element => {
                    const control = element.closest('input,textarea,select,button,[role="combobox"],[aria-disabled]');
                    if (!control) return false;
                    return Boolean(control.disabled) || control.getAttribute('aria-disabled') === 'true';
                }"""
            )
            if disabled:
                return
        except PlaywrightError:
            pass
        raise AssertionError(f"Expected mandatory dependent field {spec.label!r} to stay disabled until its parent value is selected.")

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
            self.page.wait_for_load_state("domcontentloaded", timeout=1_000)
        except TimeoutError:
            pass

    @staticmethod
    def _expect_text_value(control: Locator, value: str, label: str) -> None:
        try:
            expect(control).to_have_value(value, timeout=2_000)
        except AssertionError:
            # Some custom controls expose text content rather than input value.
            expect(control).to_contain_text(value, timeout=2_000)


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


def existing_locator_candidates(candidates: list[tuple[str, Locator]]) -> list[tuple[str, Locator]]:
    existing = []
    for label, locator in candidates:
        try:
            if locator.count() > 0:
                existing.append((label, locator))
        except PlaywrightError:
            continue
    return existing


def _console_debug(message: str) -> None:
    if os.getenv("E2E_CONSOLE_STEPS", "").strip().lower() in {"1", "true", "yes", "on"}:
        print(f"[DEBUG] {message}", flush=True)
