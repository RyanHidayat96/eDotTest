from __future__ import annotations

import pytest

from edot_qa.mobile.device import adb_devices, clear_app_data, command_available, package_installed, ready_device
from edot_qa.reporting.allure_helpers import allure_step, attach_json


pytestmark = [
    pytest.mark.mobile,
    pytest.mark.requires_credentials,
    pytest.mark.requires_device,
    pytest.mark.requires_maestro,
    pytest.mark.requires_mobile_app,
]


def test_ework_login_displays_dashboard(mobile_settings, run_maestro_flow):
    with allure_step("Validate mobile login prerequisites", screenshot=False):
        missing = mobile_settings.missing_login_requirements()
        if missing:
            pytest.skip(f"Missing mobile login environment values: {', '.join(missing)}")
        if not command_available(mobile_settings.maestro_cli):
            pytest.skip("Maestro CLI not installed or not on PATH")
        if not command_available(mobile_settings.adb_command):
            pytest.skip("ADB command not installed or not on PATH")

    with allure_step("Validate adb ready device", data=mobile_settings.as_safe_dict(), screenshot=False):
        devices = adb_devices(mobile_settings.adb_command, timeout_seconds=5)
        device = ready_device(devices, mobile_settings.mobile_device_id)
        if device is None:
            pytest.skip("No adb-visible ready mobile device")
        attach_json("mobile-login-device", {"serial": device.serial, "status": device.status})

    with allure_step("Validate eWork app installed", data={"package": mobile_settings.ework_app_id}, screenshot=False):
        if not package_installed(
            mobile_settings.ework_app_id or "",
            mobile_settings.adb_command,
            device_id=mobile_settings.mobile_device_id or device.serial,
            timeout_seconds=5,
        ):
            pytest.skip("eWork SFA app not installed or EWORK_APP_ID is incorrect")

    with allure_step("Reset eWork app data", data={"package": mobile_settings.ework_app_id}, screenshot=False):
        reset_output = clear_app_data(
            mobile_settings.ework_app_id or "",
            mobile_settings.adb_command,
            device_id=mobile_settings.mobile_device_id or device.serial,
            timeout_seconds=10,
        )
        attach_json("mobile-login-reset", {"package": mobile_settings.ework_app_id, "result": reset_output})

    run_maestro_flow("login.yaml")
