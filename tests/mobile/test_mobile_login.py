from __future__ import annotations

import pytest

from edot_qa.mobile.scenarios.login import MobileLoginScenario


pytestmark = [
    pytest.mark.mobile,
    pytest.mark.requires_credentials,
    pytest.mark.requires_device,
    pytest.mark.requires_maestro,
    pytest.mark.requires_mobile_app,
]


def test_ework_login_displays_dashboard(mobile_settings, run_maestro_flow, run_mobile_scenario):
    scenario = MobileLoginScenario(mobile_settings, run_maestro_flow)
    run_mobile_scenario(scenario.run)
