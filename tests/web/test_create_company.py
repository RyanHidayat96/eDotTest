from __future__ import annotations

import pytest

from edot_qa.ai.test_data import generate_test_data
from edot_qa.config import load_settings
from edot_qa.reporting.allure_helpers import attach_json, attach_text
from edot_qa.web.company_registration import CompanyRegistrationData
from edot_qa.web.pages.companies_page import CompaniesPage
from edot_qa.web.session_state import has_storage_state


def _login_ready() -> bool:
    settings = load_settings()
    return settings.has_esuite_credentials or has_storage_state(settings)


pytestmark = [
    pytest.mark.web,
    pytest.mark.requires_credentials,
    pytest.mark.skipif(
        not _login_ready(),
        reason="Missing ESUITE_EMAIL/ESUITE_PASSWORD and no storage_state file exists",
    ),
]


def test_register_company_step_one_requires_valid_data(settings, authenticated_page):
    generated_data = generate_test_data()
    registration = CompanyRegistrationData.from_generated_test_data(generated_data)
    attach_json("company-registration-data", registration.as_allure_payload())

    wizard = CompaniesPage(authenticated_page, settings).open_register_company_wizard()
    wizard.expect_next_disabled_until_step_one_valid(registration)


@pytest.mark.requires_cleanup
def test_create_company_three_step_wizard_with_ai_data(settings, authenticated_page):
    generated_data = generate_test_data()
    registration = CompanyRegistrationData.from_generated_test_data(generated_data)
    attach_json("company-registration-data", registration.as_allure_payload())

    primary_error: Exception | None = None
    created_company_id: str | None = None
    try:
        wizard = CompaniesPage(authenticated_page, settings).open_register_company_wizard()
        wizard.complete_three_step_registration(registration)

        manage_page = CompaniesPage(authenticated_page, settings).open_manage()
        # Tier 2: created record must display submitted company name in Manage, not only a success toast.
        manage_page.expect_company_present(registration.company_name)
        detail_page = manage_page.open_company_detail(registration.company_name)
        detail_page.expect_company_values(registration)
        created_company_id = detail_page.company_id_value()
    except Exception as error:
        primary_error = error
        raise
    finally:
        try:
            cleanup_page = CompaniesPage(authenticated_page, settings).open_manage()
            cleanup_page.delete_company_if_present(registration.company_name)
            cleanup_page.expect_company_absent(registration.company_name, company_id=created_company_id)
        except Exception as cleanup_error:
            attach_text("company-cleanup-error", str(cleanup_error))
            if primary_error is None:
                raise
