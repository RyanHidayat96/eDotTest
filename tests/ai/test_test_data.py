from __future__ import annotations

import json

import pytest

from edot_qa.ai.test_data import (
    BusinessTestData,
    GeminiModelNotFoundError,
    GeneratedTestData,
    TestDataGenerator,
    business_test_data_json_schema,
    build_prompt,
    extract_gemini_text,
    generate_test_data,
    gemini_response_schema,
)
from edot_qa.config import DEFAULT_AI_TEST_DATA_MAX_ATTEMPTS, load_settings


pytestmark = pytest.mark.ai


class FakeModelProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def generate(self, prompt: str, schema: dict, *, model: str, max_output_tokens: int) -> str:
        self.calls += 1
        assert "run_id" in prompt
        assert schema["type"] == "object"
        assert model
        assert max_output_tokens > 0
        return self.responses.pop(0)


class MissingModelProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, schema: dict, *, model: str, max_output_tokens: int) -> str:
        self.calls += 1
        raise GeminiModelNotFoundError("Gemini model not found: gemini-old")


class ApiErrorProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, schema: dict, *, model: str, max_output_tokens: int) -> str:
        self.calls += 1
        raise RuntimeError("Gemini API request failed: timed out")


VALID_PAYLOAD = {
    "company": {
        "legal_name": "PT Ritel Nusantara QA ABC12345",
        "email": "qa.company.abc12345@example.test",
        "phone": "+628123456789",
        "street_address": "Jl. Sudirman No. 10, Jakarta Selatan",
        "industry": "Retail",
    },
    "customer": {
        "name": "Budi Santoso QA ABC12345",
        "contact": "+6281299900111",
        "address": "Jl. Melati Raya No. 8, Jakarta Selatan",
    },
}


def test_faker_fallback_is_deterministic(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    settings = load_settings()
    first = TestDataGenerator(settings=settings).generate("run-step-4", attach_to_allure=False)
    second = TestDataGenerator(settings=settings).generate("run-step-4", attach_to_allure=False)

    assert first == second
    assert first.source == "faker_fallback:missing_api_key"
    assert first.data.company.email.endswith("@example.test")
    assert first.data.company.phone.startswith("+62")


def test_invalid_model_output_retries_then_uses_valid_payload(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    provider = FakeModelProvider(["not-json", json.dumps(VALID_PAYLOAD)])
    generated = TestDataGenerator(settings=load_settings(), model_provider=provider).generate(
        "abc12345",
        attach_to_allure=False,
    )

    assert provider.calls == 2
    assert generated.source == "ai_model"
    assert generated.attempts == 2
    assert generated.data.company.legal_name == VALID_PAYLOAD["company"]["legal_name"]


def test_invalid_model_output_falls_back_after_code_owned_attempt_limit(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    provider = FakeModelProvider(["{}", "{}"])
    generated = TestDataGenerator(settings=load_settings(), model_provider=provider).generate(
        "fallback-run",
        attach_to_allure=False,
    )

    assert provider.calls == DEFAULT_AI_TEST_DATA_MAX_ATTEMPTS
    assert generated.source == f"faker_fallback:invalid_model_output_after_{DEFAULT_AI_TEST_DATA_MAX_ATTEMPTS}_attempts"
    assert generated.data.company.legal_name.startswith(("PT ", "CV "))


def test_schema_rejects_extra_fields():
    payload = dict(VALID_PAYLOAD)
    payload["company"] = dict(VALID_PAYLOAD["company"], unexpected="not allowed")

    with pytest.raises(Exception):
        BusinessTestData.model_validate(payload)


def test_gemini_text_extractor_supports_generate_content_shape():
    assert (
        extract_gemini_text({"candidates": [{"content": {"parts": [{"text": json.dumps(VALID_PAYLOAD)}]}}]})
        == json.dumps(VALID_PAYLOAD)
    )


def test_gemini_key_is_preferred_for_test_data(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("GEMINI_TEST_DATA_MODEL", "gemini-3.1-flash-lite")
    settings = load_settings()

    provider = TestDataGenerator(settings=settings)._default_model_provider()

    assert provider is not None
    assert provider[1] == "gemini-3.1-flash-lite"


def test_missing_gemini_model_falls_back_without_retry(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    provider = MissingModelProvider()

    generated = TestDataGenerator(settings=load_settings(), model_provider=provider).generate(
        "missing-model-run",
        attach_to_allure=False,
    )

    assert provider.calls == 1
    assert generated.source == "faker_fallback:model_not_found"


def test_gemini_api_error_falls_back_without_retry(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    provider = ApiErrorProvider()

    generated = TestDataGenerator(settings=load_settings(), model_provider=provider).generate(
        "api-error-run",
        attach_to_allure=False,
    )

    assert provider.calls == 1
    assert generated.source == "faker_fallback:api_request_failed"


def test_prompt_keeps_guardrails():
    prompt = build_prompt("abc12345")
    assert "Return only JSON" in prompt
    assert "Do not include credentials" in prompt
    assert "abc12345" in prompt


def test_generated_data_model_forbids_extra_fields():
    with pytest.raises(Exception):
        GeneratedTestData.model_validate(
            {
                "data": VALID_PAYLOAD,
                "source": "ai_model",
                "model": "gemini-3.1-flash-lite",
                "attempts": 1,
                "run_id": "abc12345",
                "extra": "not allowed",
            }
        )


def test_model_schema_is_strict_and_flat():
    schema = business_test_data_json_schema()
    assert schema["additionalProperties"] is False
    assert "$defs" not in schema
    assert schema["properties"]["company"]["additionalProperties"] is False
    assert schema["properties"]["customer"]["additionalProperties"] is False


def test_gemini_response_schema_removes_unsupported_strict_keyword():
    schema = gemini_response_schema(business_test_data_json_schema())
    encoded = json.dumps(schema)

    assert "additionalProperties" not in encoded
    assert schema["properties"]["company"]["required"] == ["legal_name", "email", "phone", "street_address", "industry"]


def test_generate_test_data_helper_uses_fallback_without_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    generated = generate_test_data("helper-run")
    assert generated.source == "faker_fallback:missing_api_key"
    assert generated.run_id == "helper-run"
