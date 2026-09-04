from __future__ import annotations

import pytest

from edot_qa.ai.test_data import GeneratedTestData
from edot_qa.mobile.customer import MobileCustomerData, generate_mobile_customer_data
from edot_qa.mobile.device import (
    adb_devices,
    command_available,
    force_stop_app,
    package_installed,
    ready_device,
    scroll_list_to_end_and_find_texts,
    visible_texts_by_resource_id,
    wake_device,
)
from edot_qa.mobile.session_state import mobile_session_state_exists
from edot_qa.reporting.allure_helpers import allure_step, attach_json


pytestmark = pytest.mark.mobile

CUSTOMER_CARD_ADDRESS_MARKER = "__EWORK_CUSTOMER_CARD_ADDRESS__="
CUSTOMER_CARD_NAME_ID = "id.edot.ework:id/tv_name"
CUSTOMER_CARD_ADDRESS_ID = "id.edot.ework:id/tv_address"
CUSTOMER_CARD_TYPE_ID = "id.edot.ework:id/tv_first_customer_group"


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


def test_customer_card_address_marker_is_read_from_maestro_stdout():
    stdout = "noise\n__EWORK_CUSTOMER_CARD_ADDRESS__=Jl. Musyawarah\nmore noise"

    assert _customer_card_address_from_maestro_stdout(stdout) == "Jl. Musyawarah"


def test_customer_card_address_marker_ignores_maestro_command_metadata():
    stdout = "\n".join(
        [
            "Run ${console.log('__EWORK_CUSTOMER_CARD_ADDRESS__=' + output.customerAddress)} COMPLETED",
            "JsConsole: __EWORK_CUSTOMER_CARD_ADDRESS__=Jl. Musyawarah No.3A",
        ]
    )

    assert _customer_card_address_from_maestro_stdout(stdout) == "Jl. Musyawarah No.3A"


def test_customer_card_address_marker_missing_fails_clearly():
    with pytest.raises(AssertionError, match="address marker not found"):
        _customer_card_address_from_maestro_stdout("noise only")


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
        wake_device(
            mobile_settings.adb_command,
            device_id=mobile_settings.mobile_device_id or device.serial,
            timeout_seconds=10,
        )
        force_stop_app(
            mobile_settings.ework_app_id or "",
            mobile_settings.adb_command,
            device_id=mobile_settings.mobile_device_id or device.serial,
            timeout_seconds=10,
        )

    customer = generate_mobile_customer_data()
    customer_env = customer.as_maestro_env()
    create_result = run_maestro_flow("create_customer.yaml", extra_env=customer_env)
    customer_card_address = _customer_card_address_from_maestro_stdout(create_result.stdout)

    with allure_step(
        "Find created customer card from list bottom",
        data={
            "customer_name": customer.name,
            "customer_card_address": customer_card_address,
            "customer_type": mobile_settings.ework_customer_type_option_text,
            "bottom_timeout_seconds": 40,
            "search_timeout_seconds": 40,
            "max_up_swipes": 4,
            "search_identity": "customer_name",
        },
        screenshot=False,
    ):
        card_locators = [
            CUSTOMER_CARD_NAME_ID,
            CUSTOMER_CARD_ADDRESS_ID,
            CUSTOMER_CARD_TYPE_ID,
        ]
        pre_scroll_locator_texts = visible_texts_by_resource_id(
            card_locators,
            mobile_settings.adb_command,
            device_id=mobile_settings.mobile_device_id or device.serial,
            timeout_seconds=10,
        )
        attach_json("customer-card-locators-before-scroll", pre_scroll_locator_texts)
        if customer.name in pre_scroll_locator_texts[CUSTOMER_CARD_NAME_ID]:
            scroll_result = {
                "reached_end": False,
                "down_swipes": 0,
                "up_swipes": 0,
                "visible_texts": pre_scroll_locator_texts,
                "skipped_scroll": True,
            }
        else:
            result = scroll_list_to_end_and_find_texts(
                [customer.name],
                mobile_settings.adb_command,
                device_id=mobile_settings.mobile_device_id or device.serial,
                bottom_timeout_seconds=40,
                search_timeout_seconds=40,
                max_up_swipes=4,
            )
            scroll_result = {
                "reached_end": result.reached_end,
                "down_swipes": result.down_swipes,
                "up_swipes": result.up_swipes,
                "visible_texts": result.visible_texts,
                "skipped_scroll": False,
            }
        attach_json(
            "customer-list-scroll-search",
            scroll_result,
        )

    run_maestro_flow(
        "validate_customer_list_card.yaml",
        extra_env={
            **customer_env,
            "EWORK_CUSTOMER_CARD_ADDRESS": customer_card_address,
        },
    )


def _skip_or_fail_live(mobile_settings, message: str) -> None:
    if mobile_settings.edot_live:
        pytest.fail(message)
    pytest.skip(message)


def _customer_card_address_from_maestro_stdout(stdout: str) -> str:
    for line in stdout.splitlines():
        if CUSTOMER_CARD_ADDRESS_MARKER not in line:
            continue
        stripped_line = line.strip()
        if "console.log(" in stripped_line or "output.customerAddress" in stripped_line:
            continue
        if not (stripped_line.startswith(CUSTOMER_CARD_ADDRESS_MARKER) or "JsConsole:" in stripped_line):
            continue
        value = line.split(CUSTOMER_CARD_ADDRESS_MARKER, 1)[1].strip()
        if value and "COMPLETED" not in value:
            return value
    raise AssertionError("Created customer card address marker not found in Maestro output")
