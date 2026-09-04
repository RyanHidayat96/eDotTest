from __future__ import annotations

import pytest

from edot_qa.config import load_settings
from edot_qa.web.scenarios.company_registration import CompanyRegistrationScenario
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
    CompanyRegistrationScenario(authenticated_page, settings).validate_step_one_required_fields()


@pytest.mark.requires_cleanup
def test_create_company_three_step_wizard_with_ai_data(settings, authenticated_page):
    CompanyRegistrationScenario(authenticated_page, settings).create_verify_and_cleanup()
