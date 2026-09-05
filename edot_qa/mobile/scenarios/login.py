from __future__ import annotations

from dataclasses import dataclass

from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.flow_profile import EWORK_FLOW_VARIABLES
from edot_qa.mobile.maestro import MaestroResult
from edot_qa.mobile.runtime import require_login_runtime, reset_app_data_for_login
from edot_qa.mobile.scenarios.types import MaestroFlow
from edot_qa.mobile.session_state import write_mobile_session_state
from edot_qa.reporting.allure_helpers import allure_step, attach_json


@dataclass(frozen=True)
class MobileLoginScenario:
    settings: MobileSettings
    run_flow: MaestroFlow

    def run(self) -> MaestroResult:
        context = require_login_runtime(self.settings)
        reset_app_data_for_login(context)
        result = self.run_flow(
            "login.yaml",
            step_title="Login to eWork",
            expected="Dashboard is displayed",
        )

        with allure_step(
            "Store eWork mobile session state",
            data={"path": str(self.settings.ework_storage_state_path)},
            screenshot=False,
        ):
            payload = write_mobile_session_state(
                self.settings.ework_storage_state_path,
                app_id=self.settings.ework_app_id,
                device_id=context.device_id,
                dashboard_text=EWORK_FLOW_VARIABLES["EWORK_DASHBOARD_TEXT"],
            )
            attach_json("mobile-session-state", payload)
        return result
