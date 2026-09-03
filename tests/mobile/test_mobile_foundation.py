from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from edot_qa.config import ROOT_DIR
from edot_qa.mobile.config import MobileSettings, load_mobile_settings
from edot_qa.mobile.device import adb_devices, command_available, package_installed, parse_adb_devices, ready_device
from edot_qa.mobile.maestro import MaestroResult, MaestroRunner, assert_maestro_passed


pytestmark = pytest.mark.mobile


def test_mobile_settings_are_secret_safe(monkeypatch):
    monkeypatch.setenv("EWORK_APP_ID", "com.edot.ework")
    monkeypatch.setenv("EWORK_EMAIL", "user@example.test")
    monkeypatch.setenv("EWORK_PASSWORD", "secret-value")
    monkeypatch.setenv("EWORK_COMPANY_CODE", "company-code")
    monkeypatch.setenv("EWORK_LOGIN_SCREEN_TEXT", "Login")
    monkeypatch.setenv("EWORK_USERNAME_FIELD_ID", "login-email")
    monkeypatch.setenv("EWORK_PASSWORD_FIELD_ID", "login-password")
    monkeypatch.setenv("EWORK_LOGIN_BUTTON_ID", "login-submit")
    monkeypatch.setenv("EWORK_DASHBOARD_TEXT", "Dashboard")

    safe = load_mobile_settings().as_safe_dict()

    assert safe["EWORK_APP_ID"] == "com.edot.ework"
    assert safe["EWORK_EMAIL"] == "<set>"
    assert safe["EWORK_PASSWORD"] == "<set>"
    assert safe["EWORK_COMPANY_CODE"] == "<set>"
    assert safe["EWORK_DASHBOARD_TEXT"] == "Dashboard"
    assert "secret-value" not in str(safe)


def test_mobile_settings_reports_missing_login_requirements(tmp_path):
    settings = _mobile_settings(tmp_path)

    assert settings.has_login_selectors
    assert "EWORK_EMAIL" in settings.missing_login_requirements()
    assert "EWORK_PASSWORD" in settings.missing_login_requirements()


def test_adb_devices_parser_detects_ready_device():
    output = """
List of devices attached
emulator-5554	device
R58M12345	offline
"""
    devices = parse_adb_devices(output)

    assert ready_device(devices).serial == "emulator-5554"
    assert ready_device(devices, requested_serial="R58M12345") is None


def test_package_installed_checks_exact_package(monkeypatch):
    def fake_run(command, **kwargs):
        assert command == ["adb", "-s", "emulator-5554", "shell", "pm", "list", "packages", "com.example.app"]
        return subprocess.CompletedProcess(command, 0, stdout="package:com.example.app\n", stderr="")

    monkeypatch.setattr("edot_qa.mobile.device.subprocess.run", fake_run)

    assert package_installed("com.example.app", device_id="emulator-5554")


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


def test_maestro_assertion_helper_fails_pytest_on_failed_flow(tmp_path):
    result = MaestroResult(
        flow_path=tmp_path / "login.yaml",
        command=["maestro", "test", "login.yaml"],
        returncode=1,
        stdout="",
        stderr="bad selector",
    )

    with pytest.raises(AssertionError, match="Maestro flow failed"):
        assert_maestro_passed(result)


def test_mobile_login_flow_uses_run_flow_and_environment_values():
    entry_flow = (ROOT_DIR / "mobile" / "flows" / "login.yaml").read_text(encoding="utf-8")
    shared_flow = (ROOT_DIR / "mobile" / "flows" / "common" / "login.yaml").read_text(encoding="utf-8")
    combined = f"{entry_flow}\n{shared_flow}"

    assert "runFlow: common/login.yaml" in entry_flow
    assert "${EWORK_APP_ID}" in combined
    assert "${EWORK_EMAIL}" in shared_flow
    assert "${EWORK_PASSWORD}" in shared_flow
    assert "${EWORK_DASHBOARD_TEXT}" in entry_flow
    assert "@edot" not in combined.lower()


def test_mobile_flows_keep_assignment_guardrails():
    offenders = []
    for flow_path in sorted((ROOT_DIR / "mobile" / "flows").rglob("*.yaml")):
        lines = flow_path.read_text(encoding="utf-8").splitlines()
        text = "\n".join(lines)
        if "@edot" in text.lower():
            offenders.append(f"{flow_path.relative_to(ROOT_DIR)} may hardcode assignment email")
        if "password:" in text.lower():
            offenders.append(f"{flow_path.relative_to(ROOT_DIR)} may hardcode password text")

        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("- sleep") or stripped.startswith("waitForTimeout"):
                offenders.append(f"{flow_path.relative_to(ROOT_DIR)}:{index + 1} uses sleep-based wait")
            if stripped.startswith("point:") and "last resort" not in _previous_comment(lines, index).lower():
                offenders.append(f"{flow_path.relative_to(ROOT_DIR)}:{index + 1} coordinate tap lacks justification")

    assert offenders == []


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


@pytest.mark.requires_device
def test_mobile_runtime_has_adb_ready_device(mobile_settings):
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
        ework_login_screen_text="Login",
        ework_username_field_id="login-email",
        ework_password_field_id="login-password",
        ework_login_button_id="login-submit",
        ework_dashboard_text="Dashboard",
        maestro_flow_dir=flow_dir,
        maestro_output_dir=tmp_path / "maestro-output",
        allure_results_dir=tmp_path / "allure-results",
    )


def _previous_comment(lines: list[str], index: int) -> str:
    comments = []
    for candidate in lines[max(0, index - 3) : index]:
        stripped = candidate.strip()
        if stripped.startswith("#"):
            comments.append(stripped)
    return " ".join(comments)
