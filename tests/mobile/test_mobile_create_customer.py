from __future__ import annotations

import pytest

from edot_qa.ai.test_data import GeneratedTestData
from edot_qa.mobile.customer import MobileCustomerData, generate_mobile_customer_data
from edot_qa.mobile.device import adb_devices, command_available, force_stop_app, package_installed, ready_device
from edot_qa.mobile.session_state import mobile_session_state_exists
from edot_qa.reporting.allure_helpers import allure_step, attach_json


pytestmark = pytest.mark.mobile


def test_mobile_customer_data_maps_ai_payload():
    generated = GeneratedTestData.model_validate(
        {
            "data": {
                "company": {
                    "legal_name": "PT Ritel Nusantara",
                    "email": "qa.company@example.test",
                    "phone": "+628123456789",
                    "street_address": "Jl. Sudirman No. 10, Jakarta Selatan",
                    "industry": "Retail",
                },
                "customer": {
                    "name": "Budi Santoso QA CUSTOMER",
                    "contact": "+6281299900111",
                    "address": "Jl. Melati Raya No. 8, Jakarta Selatan",
                },
            },
            "source": "faker_fallback:unit",
            "model": None,
            "attempts": 0,
            "run_id": "mobile-customer-unit",
        }
    )
    customer = MobileCustomerData.from_generated_test_data(generated)

    assert customer.name.startswith("Budi Santoso QA CUSTOMER QA ")
    assert customer.name.endswith("2E90892D")
    assert customer.contact == "+6281299900111"
    assert customer.address == "Jl. Melati Raya No. 8, Jakarta Selatan"
    assert customer.ktp_number.isdigit()
    assert len(customer.ktp_number) == 16
    assert customer.as_maestro_env() == {
        "EWORK_CUSTOMER_NAME": customer.name,
        "EWORK_CUSTOMER_CONTACT": "81299900111",
        "EWORK_CUSTOMER_CONTACT_PERSON": customer.name,
        "EWORK_CUSTOMER_ADDRESS": "Jl. Melati Raya No. 8, Jakarta Selatan",
        "EWORK_CUSTOMER_KTP_NUMBER": customer.ktp_number,
    }


def test_mobile_customer_contact_uses_phone_when_ai_returns_email():
    generated = GeneratedTestData.model_validate(
        {
            "data": {
                "company": {
                    "legal_name": "PT Ritel Nusantara",
                    "email": "qa.company@example.test",
                    "phone": "+628123456789",
                    "street_address": "Jl. Sudirman No. 10, Jakarta Selatan",
                    "industry": "Retail",
                },
                "customer": {
                    "name": "Budi Santoso",
                    "contact": "budi@example.test",
                    "address": "Jl. Melati Raya No. 8, Jakarta Selatan",
                },
            },
            "source": "ai_model",
            "model": "gemini-3.1-flash-lite",
            "attempts": 1,
            "run_id": "mobile-email-contact",
        }
    )

    customer = MobileCustomerData.from_generated_test_data(generated)

    assert customer.contact.startswith("+62")
    assert customer.contact[1:].isdigit()
    assert customer.contact != "budi@example.test"


@pytest.mark.requires_credentials
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_mobile_app
def test_ework_create_customer_appears_with_correct_data(mobile_settings, run_maestro_flow):
    with allure_step("Validate mobile customer prerequisites", screenshot=False):
        missing = mobile_settings.missing_customer_requirements()
        if missing:
            _skip_or_fail_live(
                mobile_settings,
                f"Missing mobile customer environment values: {', '.join(missing)}",
            )
        if not command_available(mobile_settings.maestro_cli):
            _skip_or_fail_live(mobile_settings, "Maestro CLI not installed or not on PATH")
        if not command_available(mobile_settings.adb_command):
            _skip_or_fail_live(mobile_settings, "ADB command not installed or not on PATH")

    with allure_step("Validate adb ready device", data=mobile_settings.as_safe_dict(), screenshot=False):
        devices = adb_devices(mobile_settings.adb_command, timeout_seconds=5)
        device = ready_device(devices, mobile_settings.mobile_device_id)
        if device is None:
            _skip_or_fail_live(mobile_settings, "No adb-visible ready mobile device")
        attach_json("mobile-create-customer-device", {"serial": device.serial, "status": device.status})

    with allure_step("Validate eWork app installed", data={"package": mobile_settings.ework_app_id}, screenshot=False):
        if not package_installed(
            mobile_settings.ework_app_id or "",
            mobile_settings.adb_command,
            device_id=mobile_settings.mobile_device_id or device.serial,
            timeout_seconds=5,
        ):
            _skip_or_fail_live(mobile_settings, "eWork SFA app not installed or EWORK_APP_ID is incorrect")

    with allure_step(
        "Validate eWork mobile session state",
        data={"path": str(mobile_settings.ework_storage_state_path)},
        screenshot=False,
    ):
        if not mobile_session_state_exists(
            mobile_settings.ework_storage_state_path,
            app_id=mobile_settings.ework_app_id,
        ):
            _skip_or_fail_live(
                mobile_settings,
                "Missing eWork mobile storage state. Run npm run test:mobile:login first.",
            )

    with allure_step("Start eWork from stored mobile session", data={"package": mobile_settings.ework_app_id}, screenshot=False):
        force_stop_app(
            mobile_settings.ework_app_id or "",
            mobile_settings.adb_command,
            device_id=mobile_settings.mobile_device_id or device.serial,
            timeout_seconds=10,
        )

    customer = generate_mobile_customer_data()
    # Tier 2: create-customer flow asserts card-visible persisted values after save.
    run_maestro_flow("create_customer.yaml", extra_env=customer.as_maestro_env())


def _skip_or_fail_live(mobile_settings, message: str) -> None:
    if mobile_settings.edot_live:
        pytest.fail(message)
    pytest.skip(message)
