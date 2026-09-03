from __future__ import annotations

from urllib.parse import urlparse

import pytest

from edot_qa.config import load_settings
from edot_qa.reporting.allure_helpers import attach_json
from edot_qa.web.pages.dashboard_page import DashboardPage
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


def test_esuite_login_shows_dashboard_greeting(settings, esuite_storage_state, authenticated_page):
    dashboard = DashboardPage(authenticated_page, settings)
    dashboard.open()
    dashboard.expect_loaded()

    parsed_url = urlparse(authenticated_page.url)
    attach_json(
        "login-verification",
        {
            "assertion": "Welcome Back, greeting is visible",
            "storage_state_path": str(esuite_storage_state),
            "current_location": f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}",
        },
    )
