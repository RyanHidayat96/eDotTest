from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Locator, TimeoutError, expect

from edot_qa.reporting.allure_helpers import allure_step, attach_json, attach_page_evidence, show_dev_inputs_in_reports
from edot_qa.web.base_page import BasePage


EMAIL_OR_USERNAME = re.compile(r"use email or username", re.I)
EMAIL_FIELD = re.compile(r"(email|e-mail|username|user name)", re.I)
PASSWORD_FIELD = re.compile(r"(password|kata sandi)", re.I)
SUBMIT_ACTION = re.compile(r"^(continue|next|submit|login|log in|sign in|masuk|lanjut)$", re.I)
DELIBERATE_WRONG_LOGIN_BUTTON_ACTION = re.compile(r"^edot deliberate missing login button$", re.I)


class LoginPage(BasePage):
    def open(self) -> None:
        with allure_step(
            "Open eSuite login page",
            page=self.page,
            data={"base_url": self.settings.esuite_base_url},
            screenshot=True,
        ):
            self.page.goto(self.settings.esuite_base_url)
            self.page.wait_for_load_state("domcontentloaded")

    @property
    def use_email_or_username_button(self) -> Locator:
        role_button = self.page.get_by_role("button", name=EMAIL_OR_USERNAME).first
        # Text fallback is justified because the assignment names this exact login action.
        exact_text = self.page.get_by_text("Use Email or Username", exact=True).first
        return self.first_visible(
            [
                ("button named Use Email or Username", role_button),
                ("assignment-required action text", exact_text),
            ],
            "Use Email or Username action",
            timeout_ms=10_000,
        )

    @property
    def email_or_username_input(self) -> Locator:
        return self.first_visible(
            [
                ("textbox named email or username", self.page.get_by_role("textbox", name=EMAIL_FIELD).first),
                ("placeholder email or username", self.page.get_by_placeholder(EMAIL_FIELD).first),
                ("input with stable email name", self.page.locator("input[name*='email' i]").first),
                ("input with stable username name", self.page.locator("input[name*='username' i]").first),
                ("input with stable email type", self.page.locator("input[type='email']").first),
            ],
            "email or username input",
            timeout_ms=10_000,
        )

    @property
    def password_input(self) -> Locator:
        return self.first_visible(
            [
                ("textbox named password", self.page.get_by_role("textbox", name=PASSWORD_FIELD).first),
                ("placeholder password", self.page.get_by_placeholder(PASSWORD_FIELD).first),
                ("input with stable password name", self.page.locator("input[name*='password' i]").first),
                ("input with stable password type", self.page.locator("input[type='password']").first),
            ],
            "password input",
            timeout_ms=10_000,
        )

    @property
    def submit_button(self) -> Locator:
        return self.first_visible(
            [
                ("button with login submit action", self.page.get_by_role("button", name=SUBMIT_ACTION).first),
                ("button with stable submit type", self.page.locator("button[type='submit']").first),
                ("input with stable submit type", self.page.locator("input[type='submit']").first),
            ],
            "form submit action",
            timeout_ms=10_000,
        )

    def choose_email_or_username(self) -> None:
        with allure_step("Choose email or username login method", page=self.page, screenshot=True):
            self.use_email_or_username_button.click()

    def submit_email(self, email: str) -> None:
        visible_email = email if show_dev_inputs_in_reports() else "<redacted>"
        with allure_step(
            "Input eSuite email or username",
            page=self.page,
            force=True,
        ):
            self.email_or_username_input.fill(email)
            attach_json("Inputs", {"fields": {"email_or_username": visible_email}}, redact=False)
            attach_page_evidence("Email or username input", self.page, screenshot=True)
            self.submit_button.click()

    def submit_password(self, password: str) -> None:
        visible_password = password if show_dev_inputs_in_reports() else "<redacted>"
        with allure_step(
            "Input eSuite password",
            page=self.page,
            force=True,
        ):
            self.password_input.fill(password)
            attach_json("Inputs", {"fields": {"password": visible_password}}, redact=False)
            attach_page_evidence("Password input", self.page, screenshot=True)
            self.submit_button.click()

    def wait_for_esuite_return(self) -> None:
        expected_host = urlparse(self.settings.esuite_base_url).netloc

        def is_esuite_url(url: str) -> bool:
            return urlparse(url).netloc == expected_host

        with allure_step(
            "Wait for redirect back to eSuite",
            page=self.page,
            data={"expected_host": expected_host},
            screenshot=True,
        ):
            try:
                self.page.wait_for_url(is_esuite_url, timeout=20_000)
            except TimeoutError:
                current_host = urlparse(self.page.url).netloc
                raise AssertionError(
                    f"Expected redirect back to {expected_host}; current host is {current_host}"
                ) from None
            self.page.wait_for_load_state("domcontentloaded")

    def expect_deliberate_wrong_login_button_locator(self) -> None:
        with allure_step(
            "Deliberate web failure: wrong login button locator",
            page=self.page,
            data={"wrong_locator": "role=button[name='edot deliberate missing login button']"},
            screenshot=True,
        ):
            wrong_button = self.page.get_by_role("button", name=DELIBERATE_WRONG_LOGIN_BUTTON_ACTION)
            expect(wrong_button).to_be_visible(timeout=1_000)

    def login(self, email: str, password: str) -> None:
        with allure_step("Login to eSuite", page=self.page, data={"email": email, "password": password}, screenshot=False):
            self.open()
            self.choose_email_or_username()
            self.submit_email(email)
            self.submit_password(password)
            self.wait_for_esuite_return()
