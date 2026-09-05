from __future__ import annotations

import re
from pathlib import Path

from edot_qa.mobile import config as mobile_config
from edot_qa.mobile import maestro as mobile_maestro
from edot_qa.mobile import runtime as mobile_runtime
from edot_qa.mobile.device import MobileDevice
from edot_qa.mobile.flow_profile import EWORK_FLOW_VARIABLES
from edot_qa.mobile.maestro import MaestroResult, MaestroRunner


ROOT_DIR = Path(__file__).resolve().parents[2]
FLOW_VARIABLE_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
SCREENSHOT_PATTERN = re.compile(r"takeScreenshot:\s+([^\s]+)")
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


def test_mobile_flow_screenshots_are_grouped_by_page():
    flow_root = ROOT_DIR / "mobile" / "flows"
    flow_files = {str(path.relative_to(flow_root)).replace("\\", "/") for path in flow_root.rglob("*.yaml")}
    screenshots = {
        str(path.relative_to(flow_root)).replace("\\", "/"): SCREENSHOT_PATTERN.findall(
            path.read_text(encoding="utf-8")
        )
        for path in flow_root.rglob("*.yaml")
    }

    assert flow_files == {
        "login.yaml",
        "validate_customer_list_card.yaml",
        "common/create_customer_basic.yaml",
        "common/create_customer_documents.yaml",
        "common/create_customer_locations.yaml",
        "common/login.yaml",
        "common/open_customer_list.yaml",
    }
    assert screenshots["login.yaml"] == [
        "reports/maestro-screenshots/login/01-open-ework-app-expected-login-page-is-displayed",
        "reports/maestro-screenshots/login/02-enter-ework-login-credentials-expected-company-id-username-and-password-fields-are-filled",
        "reports/maestro-screenshots/login/03-submit-ework-login-expected-dashboard-is-displayed",
    ]
    assert screenshots["common/login.yaml"] == []
    assert screenshots["common/create_customer_basic.yaml"] == [
        "reports/maestro-screenshots/create_customer_basic/01-open-new-customer-registration-expected-basic-customer-form-is-displayed",
        "reports/maestro-screenshots/create_customer_basic/02-enter-basic-customer-information-expected-outlet-contact-channel-and-customer-type-are-filled",
        "reports/maestro-screenshots/create_customer_basic/03-continue-to-locations-page-expected-locations-form-is-displayed",
    ]
    assert screenshots["common/create_customer_locations.yaml"] == [
        "reports/maestro-screenshots/create_customer_locations/01-open-locations-page-expected-location-form-is-displayed",
        "reports/maestro-screenshots/create_customer_locations/02-enter-customer-location-information-expected-current-location-address-and-location-dropdowns-are-filled",
        "reports/maestro-screenshots/create_customer_locations/03-continue-to-documents-page-expected-ktp-document-form-is-displayed",
    ]
    assert screenshots["common/create_customer_documents.yaml"] == [
        "reports/maestro-screenshots/create_customer_documents/01-open-documents-page-expected-ktp-form-is-displayed",
        "reports/maestro-screenshots/create_customer_documents/02-enter-ktp-document-information-expected-ktp-number-is-filled-and-attachment-preview-is-displayed",
        "reports/maestro-screenshots/create_customer_documents/03-open-signature-page-expected-signature-canvas-is-displayed",
        "reports/maestro-screenshots/create_customer_documents/04-sign-and-submit-customer-registration-expected-success-message-is-displayed",
        "reports/maestro-screenshots/create_customer_documents/05-open-new-customer-list-expected-new-customer-list-page-is-displayed",
    ]
    assert screenshots["validate_customer_list_card.yaml"] == [
        "reports/maestro-screenshots/validate_customer_list_card/01-verify-created-customer-card-expected-name-address-and-customer-type-match-submitted-data",
    ]
    assert "outlet-name-entered" not in str(screenshots)
    assert "province-selected" not in str(screenshots)


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


def test_passed_maestro_result_attaches_only_screenshots(monkeypatch, tmp_path):
    attached_json: list[str] = []
    attached_png: list[str] = []
    screenshot = tmp_path / "01-open-ework-app-expected-login-page-is-displayed.png"
    screenshot.write_bytes(b"png")
    monkeypatch.setattr(mobile_maestro, "allure", None)
    monkeypatch.setattr(mobile_maestro, "attach_json", lambda name, payload, **kwargs: attached_json.append(name))
    monkeypatch.setattr(mobile_maestro, "attach_png", lambda name, image: attached_png.append(name))

    runner = MaestroRunner(_mobile_settings())
    result = MaestroResult(
        flow_path=Path("login.yaml"),
        command=["maestro", "test", "login.yaml"],
        returncode=0,
        stdout="debug output",
        stderr="",
    )

    runner.attach_result(result, screenshot_dir=tmp_path, flow_inputs={})

    assert attached_json == []
    assert attached_png == ["Screenshot - Open eWork app. Expected: Login page is displayed"]


def test_maestro_result_attaches_inputs_to_matching_screenshot_step(monkeypatch, tmp_path):
    attached_json: list[tuple[str, object]] = []
    attached_png: list[str] = []
    screenshot = tmp_path / "02-enter-ework-login-credentials-expected-company-id-username-and-password-fields-are-filled.png"
    screenshot.write_bytes(b"png")
    monkeypatch.setattr(mobile_maestro, "allure", None)
    monkeypatch.setattr(
        mobile_maestro,
        "attach_json",
        lambda name, payload, **kwargs: attached_json.append((name, payload)),
    )
    monkeypatch.setattr(mobile_maestro, "attach_png", lambda name, image: attached_png.append(name))

    runner = MaestroRunner(_mobile_settings())
    result = MaestroResult(
        flow_path=Path("login.yaml"),
        command=["maestro", "test", "login.yaml"],
        returncode=0,
        stdout="",
        stderr="",
    )
    flow_inputs = {"fields": {"Username": "qa.user", "Password": "it.QA2025"}}

    runner.attach_result(result, screenshot_dir=tmp_path, flow_inputs=flow_inputs)

    expected_step = "Enter eWork login credentials. Expected: Company ID, username, and password fields are filled"
    assert attached_json == [(f"Inputs - {expected_step}", flow_inputs)]
    assert attached_png == [f"Screenshot - {expected_step}"]


def test_failed_maestro_result_keeps_single_diagnostic_attachment(monkeypatch, tmp_path):
    attached_json: list[str] = []
    attached_png: list[str] = []
    monkeypatch.setattr(mobile_maestro, "allure", None)
    monkeypatch.setattr(mobile_maestro, "attach_json", lambda name, payload, **kwargs: attached_json.append(name))
    monkeypatch.setattr(mobile_maestro, "attach_png", lambda name, image: attached_png.append(name))
    monkeypatch.setattr(mobile_maestro, "capture_device_screenshot", lambda *args, **kwargs: b"png")

    runner = MaestroRunner(_mobile_settings())
    result = MaestroResult(
        flow_path=Path("login.yaml"),
        command=["maestro", "test", "login.yaml"],
        returncode=1,
        stdout="debug output",
        stderr="wrong locator",
    )

    runner.attach_result(result, screenshot_dir=tmp_path, flow_inputs={})

    assert attached_json == ["Failure diagnostics"]
    assert attached_png == ["Failure screenshot"]


def _mobile_settings() -> mobile_config.MobileSettings:
    return mobile_config.MobileSettings(
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
