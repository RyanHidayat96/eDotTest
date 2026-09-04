from __future__ import annotations

import pytest

from edot_qa.config import load_settings
from edot_qa.web.scenarios.login import EsuiteLoginScenario


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
    EsuiteLoginScenario(page, settings).run()
