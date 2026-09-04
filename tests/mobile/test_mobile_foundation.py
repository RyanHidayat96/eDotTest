from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from edot_qa.config import ROOT_DIR
from edot_qa.mobile.config import MobileSettings, load_mobile_settings
from edot_qa.mobile.device import (
    adb_devices,
    capture_device_screenshot,
    clear_app_data,
    command_available,
    package_installed,
    parse_adb_devices,
    ready_device,
)
from edot_qa.mobile.maestro import MaestroResult, MaestroRunner, assert_maestro_passed


pytestmark = pytest.mark.mobile


def test_mobile_settings_are_secret_safe(monkeypatch):
    monkeypatch.setenv("EDOT_LIVE", "true")
    monkeypatch.setenv("EWORK_APP_ID", "id.edot.ework")
    monkeypatch.setenv("EWORK_EMAIL", "user@example.test")
    monkeypatch.setenv("EWORK_PASSWORD", "secret-value")
    monkeypatch.setenv("EWORK_COMPANY_NAME", "PT Example")
    monkeypatch.setenv("EWORK_COMPANY_CODE", "company-code")
    monkeypatch.setenv("EWORK_LOGIN_SCREEN_TEXT", "Login")
    monkeypatch.setenv("EWORK_COMPANY_ID_FIELD_ID", "company-id")
    monkeypatch.setenv("EWORK_USERNAME_FIELD_ID", "login-email")
    monkeypatch.setenv("EWORK_PASSWORD_FIELD_ID", "login-password")
    monkeypatch.setenv("EWORK_LOGIN_BUTTON_ID", "login-submit")
    monkeypatch.setenv("EWORK_DASHBOARD_TEXT", "Dashboard")
    monkeypatch.setenv("EWORK_CUSTOMERS_MENU_ID", "customers-menu")
    monkeypatch.setenv("EWORK_CUSTOMERS_MENU_TEXT", "New Customer")
    monkeypatch.setenv("EWORK_ADD_CUSTOMER_BUTTON_ID", "customer-add")
    monkeypatch.setenv("EWORK_CUSTOMER_NAME_FIELD_ID", "customer-name")
    monkeypatch.setenv("EWORK_CUSTOMER_CONTACT_FIELD_ID", "customer-contact")
    monkeypatch.setenv("EWORK_CUSTOMER_CONTACT_PERSON_FIELD_ID", "customer-contact-person")
    monkeypatch.setenv("EWORK_CUSTOMER_CHANNEL_FIELD_ID", "customer-channel")
    monkeypatch.setenv("EWORK_CUSTOMER_CHANNEL_OPTION_TEXT", "Modern Trade (MT)")
    monkeypatch.setenv("EWORK_CUSTOMER_TYPE_FIELD_ID", "customer-type")
    monkeypatch.setenv("EWORK_CUSTOMER_TYPE_OPTION_TEXT", "Semi Grosir")
    monkeypatch.setenv("EWORK_CUSTOMER_BASIC_CONTINUE_BUTTON_ID", "customer-basic-continue")
    monkeypatch.setenv("EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID", "customer-address-type")
    monkeypatch.setenv("EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT", "Delivery Address")
    monkeypatch.setenv("EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID", "customer-current-location")
    monkeypatch.setenv("EWORK_CUSTOMER_LOCATION_APPLY_BUTTON_ID", "customer-location-apply")
    monkeypatch.setenv("EWORK_CUSTOMER_PROVINCE_FIELD_TEXT", "Choose Province")
    monkeypatch.setenv("EWORK_CUSTOMER_PROVINCE_OPTION_TEXT", "DKI JAKARTA")
    monkeypatch.setenv("EWORK_CUSTOMER_CITY_FIELD_TEXT", "Choose City")
    monkeypatch.setenv("EWORK_CUSTOMER_CITY_OPTION_TEXT", "JAKARTA BARAT")
    monkeypatch.setenv("EWORK_CUSTOMER_DISTRICT_FIELD_TEXT", "Choose District")
    monkeypatch.setenv("EWORK_CUSTOMER_DISTRICT_OPTION_TEXT", "KEBON JERUK")
    monkeypatch.setenv("EWORK_CUSTOMER_SUBDISTRICT_FIELD_TEXT", "Choose Sub district")
    monkeypatch.setenv("EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT", "KEBON JERUK")
    monkeypatch.setenv("EWORK_CUSTOMER_ADDRESS_FIELD_ID", "customer-address")
    monkeypatch.setenv("EWORK_CUSTOMER_KTP_FIELD_ID", "customer-ktp")
    monkeypatch.setenv("EWORK_CUSTOMER_UPLOAD_BUTTON_ID", "customer-upload")
    monkeypatch.setenv("EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID", "customer-camera-capture")
    monkeypatch.setenv("EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID", "customer-document-submit")
    monkeypatch.setenv("EWORK_CUSTOMER_SIGNATURE_TITLE_TEXT", "Approval Signature")
    monkeypatch.setenv("EWORK_CUSTOMER_SIGNATURE_VIEW_ID", "customer-signature")
    monkeypatch.setenv("EWORK_CUSTOMER_SAVE_BUTTON_ID", "customer-register")
    monkeypatch.setenv("EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID", "customer-confirm-save")
    monkeypatch.setenv("EWORK_CUSTOMER_SUCCESS_TEXT", "Data Saved Successfully")
    monkeypatch.setenv("EWORK_CUSTOMER_SUCCESS_CONTINUE_BUTTON_ID", "customer-success-continue")
    monkeypatch.setenv("EWORK_CUSTOMER_SEARCH_FIELD_ID", "customer-search")

    safe = load_mobile_settings().as_safe_dict()

    assert safe["EWORK_APP_ID"] == "id.edot.ework"
    assert safe["EDOT_LIVE"] == "true"
    assert safe["EWORK_EMAIL"] == "<set>"
    assert safe["EWORK_PASSWORD"] == "<set>"
    assert safe["EWORK_COMPANY_NAME"] == "PT Example"
    assert safe["EWORK_COMPANY_CODE"] == "<set>"
    assert safe["EWORK_COMPANY_ID_FIELD_ID"] == "company-id"
    assert safe["EWORK_DASHBOARD_TEXT"] == "Dashboard"
    assert safe["EWORK_CUSTOMERS_MENU_TEXT"] == "New Customer"
    assert safe["EWORK_CUSTOMER_NAME_FIELD_ID"] == "customer-name"
    assert safe["EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID"] == "customer-address-type"
    assert safe["EWORK_CUSTOMER_KTP_FIELD_ID"] == "customer-ktp"
    assert safe["EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID"] == "customer-camera-capture"
    assert safe["EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID"] == "customer-document-submit"
    assert safe["EWORK_CUSTOMER_SAVE_BUTTON_ID"] == "customer-register"
    assert "secret-value" not in str(safe)


def test_mobile_settings_reads_edot_live_flag(monkeypatch):
    monkeypatch.setenv("EDOT_LIVE", "true")

    assert load_mobile_settings().edot_live is True

    monkeypatch.setenv("EDOT_LIVE", "0")

    assert load_mobile_settings().edot_live is False


def test_mobile_settings_reports_missing_login_requirements(tmp_path):
    settings = _mobile_settings(tmp_path)

    assert settings.has_login_selectors
    assert "EWORK_COMPANY_CODE" in settings.missing_login_requirements()
    assert "EWORK_EMAIL" in settings.missing_login_requirements()
    assert "EWORK_PASSWORD" in settings.missing_login_requirements()
    assert "EWORK_EMAIL" in settings.missing_customer_requirements()
    assert "EWORK_CUSTOMER_NAME_FIELD_ID" not in settings.missing_customer_requirements()
    assert "EWORK_CUSTOMERS_MENU_ID or EWORK_CUSTOMERS_MENU_TEXT" not in settings.missing_customer_requirements()


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


def test_clear_app_data_uses_device_scoped_pm_clear(monkeypatch):
    def fake_run(command, **kwargs):
        assert command == ["adb", "-s", "emulator-5554", "shell", "pm", "clear", "com.example.app"]
        return subprocess.CompletedProcess(command, 0, stdout="Success\n", stderr="")

    monkeypatch.setattr("edot_qa.mobile.device.subprocess.run", fake_run)

    assert clear_app_data("com.example.app", device_id="emulator-5554") == "Success"


def test_capture_device_screenshot_uses_exec_out_png(monkeypatch):
    def fake_run(command, **kwargs):
        assert command == ["adb", "-s", "emulator-5554", "exec-out", "screencap", "-p"]
        return subprocess.CompletedProcess(command, 0, stdout=b"\x89PNG\r\n", stderr=b"")

    monkeypatch.setattr("edot_qa.mobile.device.subprocess.run", fake_run)

    assert capture_device_screenshot(device_id="emulator-5554") == b"\x89PNG\r\n"


def test_maestro_runner_builds_device_scoped_command(tmp_path):
    settings = _mobile_settings(tmp_path, mobile_device_id="emulator-5554")
    flow_path = settings.maestro_flow_dir / "login.yaml"
    flow_path.write_text("appId: ${EWORK_APP_ID}\n---\n- launchApp\n", encoding="utf-8")

    command = MaestroRunner(settings).build_command("login.yaml")

    assert command == ["maestro", "--device", "emulator-5554", "test", str(flow_path)]


def test_maestro_runner_can_pass_cli_environment_values(tmp_path):
    settings = _mobile_settings(tmp_path, mobile_device_id="emulator-5554")
    command = MaestroRunner(settings).build_command("login.yaml", include_env_flags=True)

    assert "-e" in command
    assert "EWORK_APP_ID=id.edot.ework" in command
    assert "EWORK_LOGIN_SCREEN_TEXT=Login" in command


def test_maestro_runner_redacts_sensitive_cli_values(monkeypatch, tmp_path):
    settings = _mobile_settings(tmp_path, mobile_device_id="emulator-5554")
    flow_path = settings.maestro_flow_dir / "login.yaml"
    flow_path.write_text("appId: ${EWORK_APP_ID}\n---\n- launchApp\n", encoding="utf-8")
    monkeypatch.setattr("edot_qa.mobile.maestro.command_available", lambda _: True)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="EWORK_PASSWORD=secret-value and user@example.test failed",
            stderr="bad secret-value",
        )

    redaction_settings = MobileSettings(
        **{
            **settings.__dict__,
            "ework_email": "user@example.test",
            "ework_password": "secret-value",
            "ework_company_code": "company-code-secret",
        }
    )
    monkeypatch.setattr("edot_qa.mobile.maestro.subprocess.run", fake_run)
    monkeypatch.setattr("edot_qa.mobile.maestro.capture_device_screenshot", lambda *args, **kwargs: b"\x89PNG\r\n")

    result = MaestroRunner(redaction_settings).run_flow("login.yaml")

    assert "secret-value" not in " ".join(result.command)
    assert "secret-value" not in result.stdout
    assert "secret-value" not in result.stderr
    assert "user@example.test" not in result.stdout


def test_maestro_runner_returns_failed_result_without_swallowing(monkeypatch, tmp_path):
    settings = _mobile_settings(tmp_path)
    flow_path = settings.maestro_flow_dir / "login.yaml"
    flow_path.write_text("appId: ${EWORK_APP_ID}\n---\n- launchApp\n", encoding="utf-8")
    monkeypatch.setattr("edot_qa.mobile.maestro.command_available", lambda _: True)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="flow failed", stderr="bad selector")

    monkeypatch.setattr("edot_qa.mobile.maestro.subprocess.run", fake_run)
    monkeypatch.setattr("edot_qa.mobile.maestro.capture_device_screenshot", lambda *args, **kwargs: b"\x89PNG\r\n")

    result = MaestroRunner(settings).run_flow("login.yaml")

    assert not result.passed
    assert result.returncode == 1
    assert result.stdout == "flow failed"
    assert result.stderr == "bad selector"


def test_maestro_runner_merges_generated_data_env(monkeypatch, tmp_path):
    settings = _mobile_settings(tmp_path)
    flow_path = settings.maestro_flow_dir / "create_customer.yaml"
    flow_path.write_text("appId: ${EWORK_APP_ID}\n---\n- launchApp\n", encoding="utf-8")
    monkeypatch.setattr("edot_qa.mobile.maestro.command_available", lambda _: True)

    def fake_run(*args, **kwargs):
        assert kwargs["env"]["EWORK_CUSTOMER_NAME"] == "Budi QA"
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("edot_qa.mobile.maestro.subprocess.run", fake_run)
    monkeypatch.setattr("edot_qa.mobile.maestro.capture_device_screenshot", lambda *args, **kwargs: b"\x89PNG\r\n")

    result = MaestroRunner(settings).run_flow(
        "create_customer.yaml",
        extra_env={"EWORK_CUSTOMER_NAME": "Budi QA"},
    )

    assert result.passed


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
    assert "${EWORK_COMPANY_CODE}" in shared_flow
    assert "${EWORK_COMPANY_ID_FIELD_ID}" in shared_flow
    assert "${EWORK_EMAIL}" in shared_flow
    assert "${EWORK_PASSWORD}" in shared_flow
    assert "${EWORK_DASHBOARD_TEXT}" in entry_flow
    assert "@edot" not in combined.lower()


def test_mobile_create_customer_flow_uses_run_flow_and_customer_values():
    entry_flow = (ROOT_DIR / "mobile" / "flows" / "create_customer.yaml").read_text(encoding="utf-8")
    shared_flow = (ROOT_DIR / "mobile" / "flows" / "common" / "create_customer.yaml").read_text(encoding="utf-8")
    combined = f"{entry_flow}\n{shared_flow}"

    assert "runFlow: common/login.yaml" in entry_flow
    assert "runFlow: common/create_customer.yaml" in entry_flow
    assert "${EWORK_CUSTOMERS_MENU_TEXT}" in shared_flow
    assert "${EWORK_CUSTOMER_NAME}" in shared_flow
    assert "${EWORK_CUSTOMER_CONTACT}" in shared_flow
    assert "${EWORK_CUSTOMER_CONTACT_PERSON}" in shared_flow
    assert "${EWORK_CUSTOMER_ADDRESS}" in shared_flow
    assert "${EWORK_CUSTOMER_CHANNEL_FIELD_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_TYPE_FIELD_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_LOCATION_APPLY_BUTTON_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_PROVINCE_OPTION_TEXT}" in shared_flow
    assert "${EWORK_CUSTOMER_CITY_OPTION_TEXT}" in shared_flow
    assert "${EWORK_CUSTOMER_DISTRICT_OPTION_TEXT}" in shared_flow
    assert "${EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT}" in shared_flow
    assert "${EWORK_CUSTOMER_KTP_NUMBER}" in shared_flow
    assert "${EWORK_CUSTOMER_KTP_FIELD_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_UPLOAD_BUTTON_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_SIGNATURE_VIEW_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID}" in shared_flow
    assert "${EWORK_CUSTOMER_SUCCESS_TEXT}" in shared_flow
    assert "scrollUntilVisible:" in shared_flow
    assert "Tier 2: created customer name" in shared_flow
    assert "Tier 2: created customer address" in shared_flow
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
        edot_live=False,
        ework_app_id="id.edot.ework",
        ework_email=None,
        ework_password=None,
        ework_company_name=None,
        ework_company_code=None,
        ework_login_screen_text="Login",
        ework_company_id_field_id="company-id",
        ework_username_field_id="login-email",
        ework_password_field_id="login-password",
        ework_login_button_id="login-submit",
        ework_dashboard_text="Dashboard",
        ework_customers_menu_id="customers-menu",
        ework_customers_menu_text="New Customer",
        ework_add_customer_button_id="customer-add",
        ework_customer_name_field_id="customer-name",
        ework_customer_contact_field_id="customer-contact",
        ework_customer_contact_person_field_id="customer-contact-person",
        ework_customer_channel_field_id="customer-channel",
        ework_customer_channel_option_text="Modern Trade (MT)",
        ework_customer_type_field_id="customer-type",
        ework_customer_type_option_text="Semi Grosir",
        ework_customer_basic_continue_button_id="customer-basic-continue",
        ework_customer_address_type_field_id="customer-address-type",
        ework_customer_address_type_option_text="Delivery Address",
        ework_customer_current_location_button_id="customer-current-location",
        ework_customer_location_apply_button_id="customer-location-apply",
        ework_customer_province_field_text="Choose Province",
        ework_customer_province_option_text="DKI JAKARTA",
        ework_customer_city_field_text="Choose City",
        ework_customer_city_option_text="JAKARTA BARAT",
        ework_customer_district_field_text="Choose District",
        ework_customer_district_option_text="KEBON JERUK",
        ework_customer_subdistrict_field_text="Choose Sub district",
        ework_customer_subdistrict_option_text="KEBON JERUK",
        ework_customer_address_field_id="customer-address",
        ework_customer_ktp_field_id="customer-ktp",
        ework_customer_upload_button_id="customer-upload",
        ework_customer_camera_capture_button_id="customer-camera-capture",
        ework_customer_document_submit_button_id="customer-document-submit",
        ework_customer_signature_title_text="Approval Signature",
        ework_customer_signature_view_id="customer-signature",
        ework_customer_save_button_id="customer-register",
        ework_customer_save_confirm_button_id="customer-confirm-save",
        ework_customer_success_text="Data Saved Successfully",
        ework_customer_success_continue_button_id="customer-success-continue",
        ework_customer_search_field_id="customer-search",
        maestro_flow_dir=flow_dir,
        maestro_output_dir=tmp_path / "maestro-output",
        allure_results_dir=tmp_path / "allure-results",
        company_handoff_path=tmp_path / "handoff.json",
    )


def _previous_comment(lines: list[str], index: int) -> str:
    comments = []
    for candidate in lines[max(0, index - 3) : index]:
        stripped = candidate.strip()
        if stripped.startswith("#"):
            comments.append(stripped)
    return " ".join(comments)
