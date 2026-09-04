from __future__ import annotations

import pytest

from edot_qa.ai.test_data import GeneratedTestData
from edot_qa.mobile.customer import MobileCustomerData
from edot_qa.mobile.customer_list import (
    CUSTOMER_CARD_ADDRESS_ID,
    CUSTOMER_CARD_NAME_ID,
    CUSTOMER_CARD_TYPE_ID,
    customer_card_address_from_maestro_logs,
    customer_card_address_from_maestro_stdout,
    customer_card_values_visible,
)
from edot_qa.mobile.scenarios.create_customer import MobileCreateCustomerScenario


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
    assert customer.contact_person != customer.name
    assert customer.contact_person == "Bima QA PIC 849275"
    assert customer.address == "Jl. Melati Raya No. 8, Jakarta Selatan"
    assert customer.ktp_number.isdigit()
    assert len(customer.ktp_number) == 16
    assert customer.as_maestro_env() == {
        "EWORK_CUSTOMER_NAME": customer.name,
        "EWORK_CUSTOMER_CONTACT": "81299900111",
        "EWORK_CUSTOMER_CONTACT_PERSON": "Bima QA PIC 849275",
        "EWORK_CUSTOMER_KTP_NUMBER": customer.ktp_number,
    }
    allure_payload = customer.as_allure_payload()
    assert allure_payload["generated_customer"]["address"] == "Jl. Melati Raya No. 8, Jakarta Selatan"
    assert allure_payload["mobile_address_mapping"]["generated_address_directly_entered"] is False


def test_mobile_customer_persistence_payload_distinguishes_generated_and_persisted_address():
    customer = MobileCustomerData(
        name="Budi QA",
        contact="+6281299900111",
        contact_person="Raka QA PIC 123456",
        address="Jl. Generated From AI",
        ktp_number="3175070101909999",
        run_id="mobile-address-map",
        source="faker_fallback:unit",
    )

    payload = customer.as_persistence_payload("Jl. Saved From Location")

    assert payload["generated_customer"]["address"] == "Jl. Generated From AI"
    assert payload["persisted_customer"]["address"] == "Jl. Saved From Location"
    assert payload["persisted_customer"]["address_source"] == "current-location address field"
    assert payload["address_mapping"]["generated_address_directly_entered"] is False
    assert payload["address_mapping"]["generated_address_equals_persisted_address"] is False


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

    assert customer_card_address_from_maestro_stdout(stdout) == "Jl. Musyawarah"


def test_customer_card_address_marker_ignores_maestro_command_metadata():
    stdout = "\n".join(
        [
            "Run ${console.log('__EWORK_CUSTOMER_CARD_ADDRESS__=' + output.customerAddress)} COMPLETED",
            "JsConsole: __EWORK_CUSTOMER_CARD_ADDRESS__=Jl. Musyawarah No.3A",
        ]
    )

    assert customer_card_address_from_maestro_stdout(stdout) == "Jl. Musyawarah No.3A"


def test_customer_card_address_marker_reads_latest_maestro_log(tmp_path):
    log_path = tmp_path / "2026-09-04_200000" / "create_customer" / "logs" / "maestro.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        (
            "Run ${console.log('__EWORK_CUSTOMER_CARD_ADDRESS__=' + output.customerAddress)} COMPLETED\n"
            "JsConsole: __EWORK_CUSTOMER_CARD_ADDRESS__=Jl. Musyawarah No.3A\n"
        ),
        encoding="utf-8",
    )

    assert customer_card_address_from_maestro_logs(tmp_path) == "Jl. Musyawarah No.3A"


def test_customer_card_address_marker_missing_fails_clearly():
    with pytest.raises(AssertionError, match="address marker not found"):
        customer_card_address_from_maestro_stdout("noise only")


def test_customer_card_visibility_requires_name_address_and_type():
    locator_texts = {
        CUSTOMER_CARD_NAME_ID: ["Budi QA"],
        CUSTOMER_CARD_ADDRESS_ID: ["Jl. Musyawarah No.3A, Jakarta"],
        CUSTOMER_CARD_TYPE_ID: ["Semi Grosir"],
    }

    assert customer_card_values_visible(
        locator_texts,
        customer_name="Budi QA",
        customer_address="Jl. Musyawarah No.3A",
        customer_type="Semi Grosir",
    )
    assert not customer_card_values_visible(
        {**locator_texts, CUSTOMER_CARD_ADDRESS_ID: []},
        customer_name="Budi QA",
        customer_address="Jl. Musyawarah No.3A",
        customer_type="Semi Grosir",
    )


@pytest.mark.requires_credentials
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_mobile_app
def test_ework_create_customer_appears_with_correct_data(mobile_settings, run_maestro_flow, run_mobile_scenario):
    scenario = MobileCreateCustomerScenario(mobile_settings, run_maestro_flow)
    run_mobile_scenario(scenario.run)
