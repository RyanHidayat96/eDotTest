from __future__ import annotations

import pytest

from edot_qa.config import load_settings
from edot_qa.web.pages.login_page import LoginPage
from edot_qa.web.scenarios.login import EsuiteLoginScenario


def _login_ready() -> bool:
    settings = load_settings()
    return settings.has_esuite_credentials


pytestmark = pytest.mark.web


@pytest.mark.requires_credentials
@pytest.mark.skipif(
    not _login_ready(),
    reason="Missing ESUITE_EMAIL/ESUITE_PASSWORD",
)
def test_esuite_login_shows_dashboard_greeting(settings, page):
    EsuiteLoginScenario(page, settings).run()


@pytest.mark.deliberate_failure
def test_web_login_wrong_button_locator_records_real_failure(settings, page) -> None:
    login_page = LoginPage(page, settings)
    login_page.open()
    login_page.choose_email_or_username()
    login_page.expect_deliberate_wrong_login_button_locator()
