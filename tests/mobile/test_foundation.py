from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from edot_qa.config import ROOT_DIR
from edot_qa.mobile.config import MobileSettings, load_mobile_settings
from edot_qa.mobile.device import adb_devices, command_available, parse_adb_devices, ready_device
from edot_qa.mobile.maestro import MaestroRunner


pytestmark = pytest.mark.mobile


def test_mobile_settings_are_secret_safe(monkeypatch):
    monkeypatch.setenv("EWORK_APP_ID", "com.edot.ework")
    monkeypatch.setenv("EWORK_EMAIL", "user@example.test")
    monkeypatch.setenv("EWORK_PASSWORD", "secret-value")
    monkeypatch.setenv("EWORK_COMPANY_CODE", "company-code")

    safe = load_mobile_settings().as_safe_dict()

    assert safe["EWORK_APP_ID"] == "com.edot.ework"
    assert safe["EWORK_EMAIL"] == "<set>"
    assert safe["EWORK_PASSWORD"] == "<set>"
    assert safe["EWORK_COMPANY_CODE"] == "<set>"
    assert "secret-value" not in str(safe)


def test_adb_devices_parser_detects_ready_device():
    output = """
List of devices attached
emulator-5554	device
R58M12345	offline
"""
    devices = parse_adb_devices(output)

    assert ready_device(devices).serial == "emulator-5554"
    assert ready_device(devices, requested_serial="R58M12345") is None


def test_maestro_runner_builds_device_scoped_command(tmp_path):
    settings = _mobile_settings(tmp_path, mobile_device_id="emulator-5554")
    flow_path = settings.maestro_flow_dir / "login.yaml"
    flow_path.write_text("appId: ${EWORK_APP_ID}\n---\n- launchApp\n", encoding="utf-8")

    command = MaestroRunner(settings).build_command("login.yaml")

    assert command == ["maestro", "--device", "emulator-5554", "test", str(flow_path)]


def test_maestro_runner_returns_failed_result_without_swallowing(monkeypatch, tmp_path):
    settings = _mobile_settings(tmp_path)
    flow_path = settings.maestro_flow_dir / "login.yaml"
    flow_path.write_text("appId: ${EWORK_APP_ID}\n---\n- launchApp\n", encoding="utf-8")
    monkeypatch.setattr("edot_qa.mobile.maestro.command_available", lambda _: True)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="flow failed", stderr="bad selector")

    monkeypatch.setattr("edot_qa.mobile.maestro.subprocess.run", fake_run)

    result = MaestroRunner(settings).run_flow("login.yaml")

    assert not result.passed
    assert result.returncode == 1
    assert result.stdout == "flow failed"
    assert result.stderr == "bad selector"


def test_mobile_login_flow_uses_run_flow_and_environment_values():
    entry_flow = (ROOT_DIR / "mobile" / "flows" / "login.yaml").read_text(encoding="utf-8")
    shared_flow = (ROOT_DIR / "mobile" / "flows" / "common" / "login.yaml").read_text(encoding="utf-8")
    combined = f"{entry_flow}\n{shared_flow}"

    assert "runFlow: common/login.yaml" in entry_flow
    assert "${EWORK_APP_ID}" in combined
    assert "${EWORK_EMAIL}" in shared_flow
    assert "${EWORK_PASSWORD}" in shared_flow
    for forbidden in ("it.qa@edot.id", "it.QA2025", "5049209", "salesmanqaauto"):
        assert forbidden not in combined


@pytest.mark.requires_maestro
@pytest.mark.requires_device
def test_mobile_runtime_has_maestro_and_adb_device(mobile_settings):
    if not command_available(mobile_settings.maestro_cli):
        pytest.skip("Maestro CLI not installed or not on PATH")
    if not command_available(mobile_settings.adb_command):
        pytest.skip("ADB command not installed or not on PATH")

    devices = adb_devices(mobile_settings.adb_command, timeout_seconds=5)
    if ready_device(devices, mobile_settings.mobile_device_id) is None:
        pytest.skip("No adb-visible ready mobile device")


def _mobile_settings(tmp_path: Path, mobile_device_id: str | None = None) -> MobileSettings:
    flow_dir = tmp_path / "flows"
    flow_dir.mkdir()
    return MobileSettings(
        maestro_cli="maestro",
        adb_command="adb",
        mobile_device_id=mobile_device_id,
        ework_app_id="com.edot.ework",
        ework_email=None,
        ework_password=None,
        ework_company_code=None,
        maestro_flow_dir=flow_dir,
        maestro_output_dir=tmp_path / "maestro-output",
        allure_results_dir=tmp_path / "allure-results",
    )
