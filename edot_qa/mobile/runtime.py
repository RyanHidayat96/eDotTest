from __future__ import annotations

from dataclasses import dataclass

from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.device import (
    MobileDevice,
    adb_devices,
    clear_app_data,
    command_available,
    force_stop_app,
    package_installed,
    ready_device,
    wake_device,
)
from edot_qa.mobile.session_state import mobile_session_state_exists
from edot_qa.reporting.allure_helpers import allure_step, attach_json


class MobilePrerequisiteError(RuntimeError):
    """Raised when live mobile prerequisites are missing."""


@dataclass(frozen=True)
class MobileRuntimeContext:
    settings: MobileSettings
    device: MobileDevice

    @property
    def device_id(self) -> str:
        return self.settings.mobile_device_id or self.device.serial


def require_login_runtime(settings: MobileSettings) -> MobileRuntimeContext:
    with allure_step("Validate mobile login prerequisites", screenshot=False):
        _require_values(settings.missing_login_requirements(), prefix="Missing mobile login environment values")
        _require_command(settings.maestro_cli, "Maestro CLI not installed or not on PATH")
        _require_command(settings.adb_command, "ADB command not installed or not on PATH")

    context = _require_ready_device(settings)
    _require_app_installed(context)
    return context


def require_customer_runtime(settings: MobileSettings) -> MobileRuntimeContext:
    with allure_step("Validate mobile customer prerequisites", screenshot=False):
        _require_values(settings.missing_customer_requirements(), prefix="Missing mobile customer environment values")
        _require_command(settings.maestro_cli, "Maestro CLI not installed or not on PATH")
        _require_command(settings.adb_command, "ADB command not installed or not on PATH")

    context = _require_ready_device(settings)
    _require_app_installed(context)
    _require_mobile_session_state(context)
    return context


def reset_app_data_for_login(context: MobileRuntimeContext) -> None:
    with allure_step("Reset eWork app data", data={"package": context.settings.ework_app_id}, screenshot=False):
        reset_output = clear_app_data(
            context.settings.ework_app_id or "",
            context.settings.adb_command,
            device_id=context.device_id,
            timeout_seconds=10,
        )
        attach_json("mobile-login-reset", {"package": context.settings.ework_app_id, "result": reset_output})


def start_app_from_stored_session(context: MobileRuntimeContext) -> None:
    with allure_step(
        "Start eWork from stored mobile session",
        data={"package": context.settings.ework_app_id},
        screenshot=False,
    ):
        wake_device(
            context.settings.adb_command,
            device_id=context.device_id,
            timeout_seconds=10,
        )
        force_stop_app(
            context.settings.ework_app_id or "",
            context.settings.adb_command,
            device_id=context.device_id,
            timeout_seconds=10,
        )


def _require_values(missing: list[str], *, prefix: str) -> None:
    if missing:
        raise MobilePrerequisiteError(f"{prefix}: {', '.join(missing)}")


def _require_command(command: str, message: str) -> None:
    if not command_available(command):
        raise MobilePrerequisiteError(message)


def _require_ready_device(settings: MobileSettings) -> MobileRuntimeContext:
    with allure_step("Validate adb ready device", data=settings.as_safe_dict(), screenshot=False):
        devices = adb_devices(settings.adb_command, timeout_seconds=5)
        device = ready_device(devices, settings.mobile_device_id)
        if device is None:
            raise MobilePrerequisiteError("No adb-visible ready mobile device")
        attach_json("mobile-device", {"serial": device.serial, "status": device.status})
        return MobileRuntimeContext(settings=settings, device=device)


def _require_app_installed(context: MobileRuntimeContext) -> None:
    with allure_step("Validate eWork app installed", data={"package": context.settings.ework_app_id}, screenshot=False):
        if not package_installed(
            context.settings.ework_app_id or "",
            context.settings.adb_command,
            device_id=context.device_id,
            timeout_seconds=5,
        ):
            raise MobilePrerequisiteError("eWork SFA app not installed or EWORK_APP_ID is incorrect")


def _require_mobile_session_state(context: MobileRuntimeContext) -> None:
    with allure_step(
        "Validate eWork mobile session state",
        data={"path": str(context.settings.ework_storage_state_path)},
        screenshot=False,
    ):
        if not mobile_session_state_exists(
            context.settings.ework_storage_state_path,
            app_id=context.settings.ework_app_id,
        ):
            raise MobilePrerequisiteError("Missing eWork mobile storage state. Run npm run test:mobile:login first.")
