from __future__ import annotations

from urllib.parse import urlparse

import pytest

from edot_qa.config import load_settings
from edot_qa.reporting.allure_helpers import allure_step, attach_json
from edot_qa.web.pages.dashboard_page import DashboardPage
from edot_qa.web.pages.login_page import LoginPage
from edot_qa.web.session_state import save_storage_state


def _login_ready() -> bool:
    settings = load_settings()
    return settings.has_esuite_credentials


pytestmark = [
    pytest.mark.web,
    pytest.mark.requires_credentials,
    pytest.mark.skipif(
        not _login_ready(),
        reason="Missing ESUITE_EMAIL/ESUITE_PASSWORD",
    ),
]


def test_esuite_login_shows_dashboard_greeting(settings, page):
    with allure_step("Login with eSuite credentials", page=page, screenshot=False):
        LoginPage(page, settings).login(settings.esuite_email or "", settings.esuite_password or "")

    with allure_step("Verify dashboard greeting after login", page=page, screenshot=True):
        dashboard = DashboardPage(page, settings)
        dashboard.expect_loaded()

    with allure_step("Persist storage state after successful login", data={"path": settings.storage_state_path}):
        save_storage_state(page.context, settings.storage_state_path)

    parsed_url = urlparse(page.url)
    attach_json(
        "login-verification",
        {
            "assertion": "Login inputs credentials and Welcome Back, greeting is visible",
            "storage_state_path": str(settings.storage_state_path),
            "current_location": f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}",
        },
    )
