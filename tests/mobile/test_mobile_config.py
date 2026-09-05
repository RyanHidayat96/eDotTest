from __future__ import annotations

import re
import subprocess
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
}


def test_versioned_ui_profile_matches_maestro_flow_contract():
    flow_variables = set()
    for flow_path in (ROOT_DIR / "mobile" / "flows").rglob("*.yaml"):
        flow_variables.update(FLOW_VARIABLE_PATTERN.findall(flow_path.read_text(encoding="utf-8")))

    assert flow_variables == set(EWORK_FLOW_VARIABLES) | DYNAMIC_FLOW_VARIABLES


def test_mobile_flow_screenshots_are_grouped_by_page():
    flow_root = ROOT_DIR / "mobile" / "flows"
    flow_files = {
        str(path.relative_to(flow_root)).replace("\\", "/")
        for path in flow_root.rglob("*.yaml")
    }
    screenshots = {
        str(path.relative_to(flow_root)).replace("\\", "/"): SCREENSHOT_PATTERN.findall(
            path.read_text(encoding="utf-8")
        )
        for path in flow_root.rglob("*.yaml")
    }

    assert flow_files == {
        "create_customer.yaml",
        "login.yaml",
        "common/create_customer_basic.yaml",
        "common/create_customer_documents.yaml",
        "common/create_customer_locations.yaml",
        "common/login.yaml",
        "common/open_customer_list.yaml",
    }
    assert {flow: len(names) for flow, names in screenshots.items()} == {
        "create_customer.yaml": 0,
        "login.yaml": 3,
        "common/create_customer_basic.yaml": 3,
        "common/create_customer_documents.yaml": 5,
        "common/create_customer_locations.yaml": 3,
        "common/login.yaml": 0,
        "common/open_customer_list.yaml": 1,
    }
    for checkpoint_names in screenshots.values():
        for checkpoint_name in checkpoint_names:
            assert re.fullmatch(
                r"\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-expected-[a-z0-9]+(?:-[a-z0-9]+)*",
                checkpoint_name,
            )
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


def test_maestro_command_writes_checkpoint_artifacts_to_its_test_output_dir(tmp_path):
    output_dir = tmp_path / "maestro-output"
    command = MaestroRunner(_mobile_settings()).build_command(
        "create_customer.yaml",
        test_output_dir=output_dir,
    )

    assert command[:4] == ["maestro", "test", "--test-output-dir", str(output_dir)]
    assert Path(command[-1]).name == "create_customer.yaml"


def test_maestro_runner_collects_checkpoint_screenshots_from_test_output(monkeypatch, tmp_path):
    attached_png: list[str] = []
    flow_path = tmp_path / "generic_customer_flow.yaml"
    flow_path.write_text("appId: id.edot.ework\n", encoding="utf-8")
    checkpoint_names = [
        "01-open-sample-page-expected-ready-state-is-displayed.png",
        "02-enter-sample-data-expected-form-fields-are-filled.png",
        "03-submit-sample-form-expected-confirmation-is-displayed.png",
    ]

    def fake_run(command, **kwargs):
        output_index = command.index("--test-output-dir") + 1
        screenshot_dir = Path(command[output_index]) / "generic_customer_flow" / "takeScreenshot"
        screenshot_dir.mkdir(parents=True)
        for checkpoint in checkpoint_names:
            (screenshot_dir / checkpoint).write_bytes(b"png")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(mobile_maestro, "allure", None)
    monkeypatch.setattr(mobile_maestro, "command_available", lambda command: True)
    monkeypatch.setattr(mobile_maestro.subprocess, "run", fake_run)
    monkeypatch.setattr(mobile_maestro, "attach_png", lambda name, image: attached_png.append(name))

    result = MaestroRunner(_mobile_settings()).run_flow(flow_path)

    assert result.passed
    assert attached_png == [
        "Screenshot - Open sample page. Expected: Ready state is displayed",
        "Screenshot - Enter sample data. Expected: Form fields are filled",
        "Screenshot - Submit sample form. Expected: Confirmation is displayed",
    ]


def test_passed_maestro_result_attaches_only_screenshots(monkeypatch, tmp_path):
    attached_json: list[str] = []
    attached_png: list[str] = []
    screenshot_dir = tmp_path / "generic_flow" / "takeScreenshot"
    screenshot_dir.mkdir(parents=True)
    screenshot = screenshot_dir / "01-open-sample-page-expected-ready-state-is-displayed.png"
    screenshot.write_bytes(b"png")
    monkeypatch.setattr(mobile_maestro, "allure", None)
    monkeypatch.setattr(mobile_maestro, "attach_json", lambda name, payload, **kwargs: attached_json.append(name))
    monkeypatch.setattr(mobile_maestro, "attach_png", lambda name, image: attached_png.append(name))

    runner = MaestroRunner(_mobile_settings())
    result = MaestroResult(
        flow_path=Path("generic_flow.yaml"),
        command=["maestro", "test", "generic_flow.yaml"],
        returncode=0,
        stdout="debug output",
        stderr="",
    )

    runner.attach_result(result, screenshot_dir=screenshot_dir, flow_inputs={})

    assert attached_json == []
    assert attached_png == ["Screenshot - Open sample page. Expected: Ready state is displayed"]


def test_maestro_result_attaches_inputs_to_matching_screenshot_step(monkeypatch, tmp_path):
    attached_json: list[tuple[str, object]] = []
    attached_png: list[str] = []
    screenshot_dir = tmp_path / "generic_flow" / "takeScreenshot"
    screenshot_dir.mkdir(parents=True)
    screenshot = screenshot_dir / "02-enter-customer-contact-details-expected-fields-are-filled.png"
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
        flow_path=Path("generic_flow.yaml"),
        command=["maestro", "test", "generic_flow.yaml"],
        returncode=0,
        stdout="",
        stderr="",
    )
    flow_inputs = {"fields": {"Contact Person": "Budi QA", "Contact": "081234567890"}}

    runner.attach_result(result, screenshot_dir=tmp_path, flow_inputs=flow_inputs)

    expected_step = "Enter customer contact details. Expected: Fields are filled"
    assert attached_json == [(f"Inputs - {expected_step}", flow_inputs)]
    assert attached_png == [f"Screenshot - {expected_step}"]


def test_maestro_result_uses_checkpoint_specific_input_payload(monkeypatch, tmp_path):
    attached_json: list[tuple[str, object]] = []
    attached_png: list[str] = []
    screenshot_dir = tmp_path / "create_customer_documents" / "takeScreenshot"
    screenshot_dir.mkdir(parents=True)
    screenshot = screenshot_dir / "04-sign-and-submit-customer-registration-expected-success-message-is-displayed.png"
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
        flow_path=Path("create_customer_documents.yaml"),
        command=["maestro", "test", "create_customer_documents.yaml"],
        returncode=0,
        stdout="",
        stderr="",
    )
    signature_payload = {"fields": {"Signature": "drawn"}}
    flow_inputs = {
        "fields": {
            "KTP": "3175070101909999",
            "Attachment": "camera capture",
            "Signature": "drawn",
        },
        "_checkpoint_inputs": {"sign-and-submit-customer-registration": signature_payload},
    }

    runner.attach_result(result, screenshot_dir=tmp_path, flow_inputs=flow_inputs)

    expected_step = "Sign and submit customer registration. Expected: Success message is displayed"
    assert attached_json == [(f"Inputs - {expected_step}", signature_payload)]
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
        flow_path=Path("generic_flow.yaml"),
        command=["maestro", "test", "generic_flow.yaml"],
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
