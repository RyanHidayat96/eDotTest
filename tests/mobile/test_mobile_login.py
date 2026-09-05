from __future__ import annotations

import pytest

from edot_qa.mobile.maestro import assert_maestro_passed
from edot_qa.mobile.runtime import require_login_runtime, reset_app_data_for_login
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


@pytest.mark.deliberate_failure
def test_mobile_login_wrong_password_locator_records_real_failure(
    mobile_settings,
    maestro_runner,
    run_mobile_scenario,
) -> None:
    def _run() -> None:
        context = require_login_runtime(mobile_settings)
        reset_app_data_for_login(context)
        result = maestro_runner.run_flow(
            "login.yaml",
            timeout_seconds=min(60, mobile_settings.mobile_flow_timeout_seconds),
            extra_env=mobile_settings.deliberate_wrong_password_field_override(),
            step_title="Deliberate mobile failure: log in with wrong password field locator",
            expected="Wrong password field locator fails and produces evidence for triage",
        )
        if result.passed:
            raise AssertionError("Deliberate mobile wrong password field locator unexpectedly passed.")
        assert_maestro_passed(result)

    run_mobile_scenario(_run)
