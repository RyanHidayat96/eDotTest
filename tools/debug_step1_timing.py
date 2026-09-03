from __future__ import annotations

import os
import time

from playwright.sync_api import sync_playwright

from edot_qa.ai.test_data import generate_test_data
from edot_qa.config import load_settings
from edot_qa.web.company_registration import CompanyRegistrationData
from edot_qa.web.pages.companies_page import CompaniesPage
from edot_qa.web.session_state import new_context


def measure(label: str, action) -> None:
    start = time.perf_counter()
    action()
    print(f"{label}: {time.perf_counter() - start:.2f}s", flush=True)


def main() -> None:
    os.environ["GEMINI_API_KEY"] = ""
    settings = load_settings()
    generated = generate_test_data("debug-step1", attach_to_allure=False)
    data = CompanyRegistrationData.from_generated_test_data(generated)

    with sync_playwright() as playwright:
        browser = getattr(playwright, settings.browser).launch(headless=True)
        context = new_context(browser, settings, use_storage_state=True)
        page = context.new_page()
        page.goto(settings.esuite_base_url, wait_until="domcontentloaded")
        wizard = CompaniesPage(page, settings).open_register_company_wizard()

        measure("initial_next_disabled", wizard.expect_next_disabled)
        measure("company_name", lambda: wizard.fill_text_field(wizard.company_name, data.company_name))
        measure("email", lambda: wizard.fill_text_field(wizard.email, data.email))
        measure("phone", lambda: wizard.fill_text_field(wizard.phone, data.phone))
        measure("industry_type", lambda: wizard.choose_field_option(wizard.industry_type, data.industry_type))
        measure("company_type", lambda: wizard.choose_field_option(wizard.company_type, data.company_type))
        measure("language", lambda: wizard.choose_field_option(wizard.language, data.language))
        measure("street_address", lambda: wizard.fill_text_field(wizard.street_address, data.street_address))
        measure("country", lambda: wizard.choose_field_option(wizard.country, data.location.country))
        measure("dependent_disabled", wizard.expect_location_dependents_disabled_after_country_only)
        measure("province", lambda: wizard.choose_field_option(wizard.province, data.location.province))
        measure("city", lambda: wizard.choose_field_option(wizard.city, data.location.city))
        measure("district", lambda: wizard.choose_field_option(wizard.district, data.location.district))
        measure("sub_district", lambda: wizard.choose_field_option(wizard.zone, data.location.zone))
        measure("postal_code", lambda: wizard.choose_or_fill_field(wizard.postal_code, data.location.postal_code))
        measure("final_next_enabled", wizard.expect_next_enabled)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
