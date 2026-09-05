from __future__ import annotations

import re
from pathlib import Path

from edot_qa.mobile import config as mobile_config
from edot_qa.mobile import runtime as mobile_runtime
from edot_qa.mobile.device import MobileDevice
from edot_qa.mobile.flow_profile import EWORK_FLOW_VARIABLES


ROOT_DIR = Path(__file__).resolve().parents[2]
FLOW_VARIABLE_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
DYNAMIC_FLOW_VARIABLES = {
    "EWORK_APP_ID",
    "EWORK_COMPANY_CODE",
    "EWORK_EMAIL",
    "EWORK_PASSWORD",
    "EWORK_CUSTOMER_NAME",
    "EWORK_CUSTOMER_CONTACT",
    "EWORK_CUSTOMER_CONTACT_PERSON",
    "EWORK_CUSTOMER_KTP_NUMBER",
    "EWORK_CUSTOMER_CARD_ADDRESS",
}


def test_versioned_ui_profile_matches_maestro_flow_contract():
    flow_variables = set()
    for flow_path in (ROOT_DIR / "mobile" / "flows").rglob("*.yaml"):
        flow_variables.update(FLOW_VARIABLE_PATTERN.findall(flow_path.read_text(encoding="utf-8")))

    assert flow_variables == set(EWORK_FLOW_VARIABLES) | DYNAMIC_FLOW_VARIABLES


def test_mobile_settings_do_not_take_locators_from_environment(monkeypatch):
    monkeypatch.setattr(mobile_config, "_load_dotenv", lambda: None)
    monkeypatch.setenv("EWORK_EMAIL", "qa.user@example.test")
    monkeypatch.setenv("EWORK_PASSWORD", "secret-value")
    monkeypatch.setenv("EWORK_COMPANY_CODE", "5120380")
    monkeypatch.setenv("EWORK_PASSWORD_FIELD_ID", "id.edot.ework:id/wrong-from-env")

    settings = mobile_config.load_mobile_settings()
    variables = settings.maestro_variables()

    assert settings.missing_login_requirements() == []
    assert variables["EWORK_PASSWORD_FIELD_ID"] == EWORK_FLOW_VARIABLES["EWORK_PASSWORD_FIELD_ID"]
    assert "secret-value" not in str(settings.as_safe_dict())


def test_customer_runtime_needs_session_not_login_credentials(monkeypatch):
    monkeypatch.setattr(mobile_config, "_load_dotenv", lambda: None)
    monkeypatch.delenv("EWORK_EMAIL", raising=False)
    monkeypatch.delenv("EWORK_PASSWORD", raising=False)
    monkeypatch.delenv("EWORK_COMPANY_CODE", raising=False)

    settings = mobile_config.load_mobile_settings()

    assert settings.missing_customer_requirements() == []


def test_customer_runtime_launches_ework_before_customer_flow(monkeypatch):
    calls: list[tuple[str, str, str | None, int]] = []

    def wake(adb_command: str, *, device_id: str | None, timeout_seconds: int) -> str:
        calls.append(("wake", adb_command, device_id, timeout_seconds))
        return ""

    def force_stop(package_name: str, adb_command: str, *, device_id: str | None, timeout_seconds: int) -> str:
        calls.append((f"force-stop:{package_name}", adb_command, device_id, timeout_seconds))
        return ""

    def launch(package_name: str, adb_command: str, *, device_id: str | None, timeout_seconds: int) -> str:
        calls.append((f"launch:{package_name}", adb_command, device_id, timeout_seconds))
        return "Events injected: 1"

    monkeypatch.setattr(mobile_runtime, "wake_device", wake)
    monkeypatch.setattr(mobile_runtime, "force_stop_app", force_stop)
    monkeypatch.setattr(mobile_runtime, "launch_app", launch)

    settings = mobile_config.MobileSettings(
        maestro_cli="maestro",
        adb_command="adb",
        mobile_device_id=None,
        mobile_flow_timeout_seconds=300,
        edot_live=True,
        prefer_company_handoff=False,
        ework_app_id="id.edot.ework",
        ework_email=None,
        ework_password=None,
        ework_company_code=None,
    )
    context = mobile_runtime.MobileRuntimeContext(
        settings=settings,
        device=MobileDevice(serial="device-1", status="device"),
    )

    mobile_runtime.start_app_from_stored_session(context)

    assert calls == [
        ("wake", "adb", "device-1", 10),
        ("force-stop:id.edot.ework", "adb", "device-1", 10),
        ("launch:id.edot.ework", "adb", "device-1", 10),
    ]
