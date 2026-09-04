from __future__ import annotations

import pytest

from edot_qa.ai.test_data import generate_test_data
from edot_qa.config import load_settings
from edot_qa.handoff import (
    CompanyHandoff,
    delete_company_handoff,
    read_company_handoff,
    write_company_handoff,
)
from edot_qa.mobile import config as mobile_config
from edot_qa.mobile.config import load_mobile_settings
from edot_qa.mobile.device import adb_devices, command_available, package_installed, ready_device
from edot_qa.mobile.maestro import MaestroRunner, assert_maestro_passed
from edot_qa.reporting.allure_helpers import allure_step, attach_json, attach_text
from edot_qa.web.company_registration import CompanyRegistrationData
from edot_qa.web.pages.companies_page import CompaniesPage
from edot_qa.web.session_state import has_storage_state


pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.mobile]


def _web_login_ready() -> bool:
    settings = load_settings()
    return settings.has_esuite_credentials or has_storage_state(settings)


def test_company_handoff_file_is_secret_free(tmp_path):
    registration = CompanyRegistrationData(
        company_name="PT Handoff Nusantara QA ABC12345",
        email="qa.company.abc12345@example.test",
        phone="+628123456789",
        industry_type="Retail",
        company_type="Retailer",
        language="English",
        street_address="Jl. Sudirman No. 10, Jakarta Selatan",
    )
    handoff = CompanyHandoff.from_registration(
        registration,
        source_run_id="abc12345",
        company_code="5120380",
    )
    path = write_company_handoff(handoff, tmp_path / "handoff.json", attach_to_allure=False)

    loaded = read_company_handoff(path)

    assert loaded == handoff
    assert loaded.as_mobile_environment() == {
        "EWORK_COMPANY_NAME": "PT Handoff Nusantara QA ABC12345",
        "EWORK_EMAIL": "qa.company.abc12345@example.test",
        "EWORK_COMPANY_CODE": "5120380",
    }
    assert loaded.trial_days == 30
    assert "password" not in path.read_text(encoding="utf-8").lower()


def test_mobile_settings_consumes_company_handoff(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_config, "_load_dotenv", lambda: None)
    monkeypatch.delenv("EWORK_EMAIL", raising=False)
    monkeypatch.delenv("EWORK_COMPANY_NAME", raising=False)
    monkeypatch.delenv("EWORK_COMPANY_CODE", raising=False)
    monkeypatch.delenv("EWORK_PREFER_HANDOFF", raising=False)
    handoff = CompanyHandoff(
        company_name="PT Handoff Nusantara QA ABC12345",
        company_email="qa.company.abc12345@example.test",
        company_code="5120380",
        source_run_id="abc12345",
    )
    path = write_company_handoff(handoff, tmp_path / "handoff.json", attach_to_allure=False)
    monkeypatch.setenv("EWORK_COMPANY_HANDOFF_PATH", str(path))

    settings = mobile_config.load_mobile_settings()

    assert settings.ework_email == "qa.company.abc12345@example.test"
    assert settings.ework_company_name == "PT Handoff Nusantara QA ABC12345"
    assert settings.ework_company_code == "5120380"
    assert "EWORK_EMAIL" not in settings.missing_login_requirements()
    assert "EWORK_COMPANY_CODE" not in settings.missing_login_requirements()


def test_mobile_settings_default_keeps_environment_identity_over_handoff(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_config, "_load_dotenv", lambda: None)
    monkeypatch.setenv("EWORK_EMAIL", "fallback-user@example.test")
    monkeypatch.setenv("EWORK_COMPANY_NAME", "Fallback Company")
    monkeypatch.setenv("EWORK_COMPANY_CODE", "fallback-code")
    monkeypatch.delenv("EWORK_PREFER_HANDOFF", raising=False)
    handoff = CompanyHandoff(
        company_name="PT Handoff Nusantara QA ABC12345",
        company_email="qa.company.abc12345@example.test",
        company_code="5120380",
        source_run_id="abc12345",
    )
    path = write_company_handoff(handoff, tmp_path / "handoff.json", attach_to_allure=False)
    monkeypatch.setenv("EWORK_COMPANY_HANDOFF_PATH", str(path))

    settings = mobile_config.load_mobile_settings()

    assert settings.prefer_company_handoff is False
    assert settings.ework_email == "fallback-user@example.test"
    assert settings.ework_company_name == "Fallback Company"
    assert settings.ework_company_code == "fallback-code"


def test_mobile_settings_handoff_mode_prefers_handoff_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_config, "_load_dotenv", lambda: None)
    monkeypatch.setenv("EWORK_EMAIL", "fallback-user@example.test")
    monkeypatch.setenv("EWORK_PASSWORD", "secret-value")
    monkeypatch.setenv("EWORK_COMPANY_NAME", "Fallback Company")
    monkeypatch.setenv("EWORK_COMPANY_CODE", "fallback-code")
    monkeypatch.setenv("EWORK_PREFER_HANDOFF", "true")
    handoff = CompanyHandoff(
        company_name="PT Handoff Nusantara QA ABC12345",
        company_email="qa.company.abc12345@example.test",
        company_code="5120380",
        source_run_id="abc12345",
    )
    path = write_company_handoff(handoff, tmp_path / "handoff.json", attach_to_allure=False)
    monkeypatch.setenv("EWORK_COMPANY_HANDOFF_PATH", str(path))

    settings = mobile_config.load_mobile_settings()

    assert settings.prefer_company_handoff is True
    assert settings.ework_email == "qa.company.abc12345@example.test"
    assert settings.ework_password == "secret-value"
    assert settings.ework_company_name == "PT Handoff Nusantara QA ABC12345"
    assert settings.ework_company_code == "5120380"
    assert "secret-value" not in str(settings.as_safe_dict())


@pytest.mark.requires_credentials
@pytest.mark.requires_cleanup
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_mobile_app
@pytest.mark.skipif(
    not _web_login_ready(),
    reason="Missing ESUITE_EMAIL/ESUITE_PASSWORD and no storage_state file exists",
)
def test_web_created_company_handoff_drives_mobile_login(settings, authenticated_page):
    with allure_step("Validate mobile handoff prerequisites", screenshot=False):
        mobile_probe = load_mobile_settings(prefer_handoff=True)
        missing_mobile = [
            item
            for item in mobile_probe.missing_login_requirements()
            if item not in {"EWORK_EMAIL", "EWORK_COMPANY_CODE"}
        ]
        if missing_mobile:
            pytest.skip(f"Missing mobile handoff login environment values: {', '.join(missing_mobile)}")
        if not command_available(mobile_probe.maestro_cli):
            pytest.skip("Maestro CLI not installed or not on PATH")
        if not command_available(mobile_probe.adb_command):
            pytest.skip("ADB command not installed or not on PATH")

    with allure_step("Validate adb device and eWork app", data=mobile_probe.as_safe_dict(), screenshot=False):
        devices = adb_devices(mobile_probe.adb_command, timeout_seconds=5)
        device = ready_device(devices, mobile_probe.mobile_device_id)
        if device is None:
            pytest.skip("No adb-visible ready mobile device")
        if not package_installed(
            mobile_probe.ework_app_id or "",
            mobile_probe.adb_command,
            device_id=mobile_probe.mobile_device_id or device.serial,
            timeout_seconds=5,
        ):
            pytest.skip("eWork SFA app not installed or EWORK_APP_ID is incorrect")

    with allure_step("Prepare handoff company data", screenshot=False):
        generated_data = generate_test_data()
        registration = CompanyRegistrationData.from_generated_test_data(generated_data)
        attach_json("handoff-company-registration-data", registration.as_allure_payload())

    primary_error: Exception | None = None
    created_company_id: str | None = None
    try:
        with allure_step("Create handoff source company on web", page=authenticated_page):
            wizard = CompaniesPage(authenticated_page, settings).open_register_company_wizard()
            wizard.complete_three_step_registration(registration)

        with allure_step("Verify handoff source company on web", page=authenticated_page, screenshot=True):
            manage_page = CompaniesPage(authenticated_page, settings).open_manage()
            # Tier 2: handoff source company must exist in Manage before mobile consumes it.
            manage_page.expect_company_present(registration.company_name)
            detail_page = manage_page.open_company_detail(registration.company_name)
            detail_page.expect_company_values(registration)
            created_company_id = detail_page.company_id_value()

        with allure_step("Create and verify company handoff file", screenshot=False):
            handoff = CompanyHandoff.from_registration(
                registration,
                source_run_id=generated_data.run_id,
                company_code=created_company_id,
            )
            write_company_handoff(handoff, mobile_probe.company_handoff_path)
            mobile_settings = load_mobile_settings(prefer_handoff=True)
            assert mobile_settings.prefer_company_handoff is True
            assert mobile_settings.ework_email == registration.email
            assert mobile_settings.ework_company_name == registration.company_name
            assert mobile_settings.ework_company_code == created_company_id

        assert_maestro_passed(MaestroRunner(mobile_settings).run_flow("login.yaml"))
    except Exception as error:
        primary_error = error
        raise
    finally:
        try:
            with allure_step(
                "Cleanup web company and handoff file",
                page=authenticated_page,
                screenshot=True,
                data={"company_name": registration.company_name, "company_id": created_company_id},
            ):
                cleanup_page = CompaniesPage(authenticated_page, settings).open_manage()
                cleanup_page.delete_company_if_present(registration.company_name)
                cleanup_page.expect_company_absent(registration.company_name, company_id=created_company_id)
                delete_company_handoff(mobile_probe.company_handoff_path)
        except Exception as cleanup_error:
            attach_text("handoff-cleanup-error", str(cleanup_error))
            if primary_error is None:
                raise
