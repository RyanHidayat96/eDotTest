from __future__ import annotations

from edot_qa.ai.test_data import GeneratedTestData
from edot_qa.web.company_registration import CompanyRegistrationData, LocationCascade


def test_company_registration_maps_ai_data_and_defaults():
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
                    "contact": "+6281299900111",
                    "address": "Jl. Melati No. 8, Jakarta Selatan",
                },
            },
            "source": "faker_fallback:missing_api_key",
            "model": None,
            "attempts": 0,
            "run_id": "run-abc12345",
        }
    )

    registration = CompanyRegistrationData.from_generated_test_data(generated)

    assert registration.company_name == "PT Ritel QA ABC12345"
    assert registration.email == "qa.company@example.test"
    assert registration.phone == "8123456789"
    assert registration.industry_type == "Retail"
    assert registration.company_type == "Retailer"
    assert registration.language == "English"
    assert registration.location == LocationCascade()
    assert registration.expected_detail_values() == {
        "name": "PT Ritel QA ABC12345",
        "industry type": "Retail",
        "company type": "Retailer",
        "address": "Jl. Sudirman No. 10, Jakarta Selatan",
        "postal code": "12190",
        "email": "qa.company@example.test",
        "phone": "8123456789",
    }


def test_company_registration_allows_env_overrides(monkeypatch):
    monkeypatch.setenv("ESUITE_COMPANY_TYPE", "Distributor")
    monkeypatch.setenv("ESUITE_COMPANY_LANGUAGE", "Indonesia")
    monkeypatch.setenv("ESUITE_COMPANY_CITY", "Jakarta Pusat")

    generated = GeneratedTestData.model_validate(
        {
            "data": {
                "company": {
                    "legal_name": "PT Data Mantap QA ABC12345",
                    "email": "qa.company@example.test",
                    "phone": "+628123456789",
                    "street_address": "Jl. Sudirman No. 10, Jakarta Selatan",
                    "industry": "Distribution",
                },
                "customer": {
                    "name": "Budi Santoso",
                    "contact": "+6281299900111",
                    "address": "Jl. Melati No. 8, Jakarta Selatan",
                },
            },
            "source": "faker_fallback:missing_api_key",
            "model": None,
            "attempts": 0,
            "run_id": "run-abc12345",
        }
    )

    registration = CompanyRegistrationData.from_generated_test_data(generated)

    assert registration.company_name == "PT Data Mantap QA ABC12345"
    assert registration.company_type == "Distributor"
    assert registration.language == "Indonesia"
    assert registration.location.city == "Jakarta Pusat"
