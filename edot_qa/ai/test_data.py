from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Protocol

from faker import Faker
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from edot_qa.config import Settings, load_settings
from edot_qa.reporting.allure_helpers import allure_step, attach_json


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INDONESIAN_PHONE_RE = re.compile(r"^\+62\d{8,13}$")


class GeminiModelNotFoundError(RuntimeError):
    pass


class CompanyData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    legal_name: str = Field(min_length=5, max_length=120)
    email: str = Field(min_length=6, max_length=120)
    phone: str = Field(min_length=10, max_length=16)
    street_address: str = Field(min_length=10, max_length=180)
    industry: str = Field(min_length=3, max_length=60)

    @field_validator("legal_name")
    @classmethod
    def legal_name_must_look_indonesian(cls, value: str) -> str:
        if not value.upper().startswith(("PT ", "CV ")):
            raise ValueError("legal_name must start with PT or CV")
        return value

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        if not EMAIL_RE.match(value):
            raise ValueError("email must be valid")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_be_indonesian(cls, value: str) -> str:
        if not INDONESIAN_PHONE_RE.match(value):
            raise ValueError("phone must use +62 format")
        return value


class CustomerData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=100)
    contact: str = Field(min_length=10, max_length=120)
    address: str = Field(min_length=10, max_length=180)

    @field_validator("contact")
    @classmethod
    def contact_must_be_valid(cls, value: str) -> str:
        if not (INDONESIAN_PHONE_RE.match(value) or EMAIL_RE.match(value)):
            raise ValueError("contact must be +62 phone or email")
        return value


class BusinessTestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: CompanyData
    customer: CustomerData


class GeneratedTestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BusinessTestData
    source: str
    model: str | None = None
    attempts: int = 0
    run_id: str


class ModelProvider(Protocol):
    def generate(self, prompt: str, schema: dict, *, model: str, max_output_tokens: int) -> str:
        """Return raw model text."""


class GeminiGenerateContentProvider:
    api_url_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def generate(self, prompt: str, schema: dict, *, model: str, max_output_tokens: int) -> str:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": gemini_response_schema(schema),
                "maxOutputTokens": max_output_tokens,
            },
        }
        request = urllib.request.Request(
            self.api_url_template.format(model=model, api_key=self.api_key),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise GeminiModelNotFoundError(
                    f"Gemini model not found: {model}. Check GEMINI_TEST_DATA_MODEL/GEMINI_TRIAGE_MODEL."
                ) from error
            raise RuntimeError(f"Gemini API request failed for model {model}: HTTP {error.code} {error.reason}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError(f"Gemini API request failed: {error}") from error
        return extract_gemini_text(body)


@dataclass
class FakerFallbackProvider:
    locale: str = "id_ID"

    def generate(self, run_id: str) -> BusinessTestData:
        fake = Faker(self.locale)
        fake.seed_instance(stable_seed(run_id))
        suffix = run_id[-8:].upper()
        company_prefix = fake.random_element(elements=("PT", "CV"))
        company_root = fake.random_element(
            elements=("Ritel", "Niaga", "Makmur")
        )
        customer_name = fake.name()
        return BusinessTestData.model_validate(
            {
                "company": {
                    "legal_name": f"{company_prefix} {company_root} QA {suffix}",
                    "email": f"qa.company.{suffix.lower()}@example.test",
                    "phone": f"+628{fake.msisdn()[-9:]}",
                    "street_address": fake.street_address(),
                    "industry": fake.random_element(
                        elements=("Retail", "Distribution", "Manufacturing", "Food and Beverage")
                    ),
                },
                "customer": {
                    "name": f"{customer_name} QA {suffix}",
                    "contact": f"+628{fake.msisdn()[-9:]}",
                    "address": fake.address().replace("\n", ", "),
                },
            }
        )


class TestDataGenerator:
    __test__ = False

    def __init__(
        self,
        settings: Settings | None = None,
        model_provider: ModelProvider | None = None,
        fallback_provider: FakerFallbackProvider | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.model_provider = model_provider
        self.fallback_provider = fallback_provider or FakerFallbackProvider()

    def generate(self, run_id: str | None = None, *, attach_to_allure: bool = True) -> GeneratedTestData:
        resolved_run_id = run_id or uuid.uuid4().hex
        provider = self.model_provider or self._default_model_provider()
        model = self.settings.gemini_test_data_model
        if isinstance(provider, tuple):
            provider, model = provider

        context = (
            allure_step(
                "Generate AI-backed test data",
                data={
                    "run_id": resolved_run_id,
                    "provider": type(provider).__name__ if provider is not None else "FakerFallbackProvider",
                    "model": model if provider is not None else None,
                    "max_attempts": self.settings.ai_test_data_max_attempts,
                },
                screenshot=False,
            )
            if attach_to_allure
            else nullcontext()
        )
        with context:
            if provider is None:
                return self._fallback(resolved_run_id, attach_to_allure=attach_to_allure, reason="missing_api_key")

            fallback_reason = f"invalid_model_output_after_{self.settings.ai_test_data_max_attempts}_attempts"
            attempt_errors: list[dict[str, str | int]] = []
            schema = business_test_data_json_schema()
            for attempt in range(1, self.settings.ai_test_data_max_attempts + 1):
                try:
                    raw_response = provider.generate(
                        build_prompt(resolved_run_id),
                        schema,
                        model=model,
                        max_output_tokens=self.settings.ai_test_data_max_output_tokens,
                    )
                    parsed_data = BusinessTestData.model_validate(json.loads(raw_response))
                    generated = GeneratedTestData(
                        data=parsed_data,
                        source="ai_model",
                        model=model,
                        attempts=attempt,
                        run_id=resolved_run_id,
                    )
                    self._attach(generated, attach_to_allure)
                    return generated
                except GeminiModelNotFoundError as error:
                    fallback_reason = "model_not_found"
                    attempt_errors.append({"attempt": attempt, "error": str(error)})
                    break
                except RuntimeError as error:
                    fallback_reason = "api_request_failed"
                    attempt_errors.append({"attempt": attempt, "error": str(error)})
                    break
                except (json.JSONDecodeError, ValidationError) as error:
                    attempt_errors.append({"attempt": attempt, "error": str(error)})

            if attempt_errors and attach_to_allure:
                attach_json("ai-test-data-generation-errors", attempt_errors)
            return self._fallback(
                resolved_run_id,
                attach_to_allure=attach_to_allure,
                reason=fallback_reason,
            )

    def _default_model_provider(self) -> tuple[ModelProvider, str] | None:
        if self.settings.gemini_api_key:
            return GeminiGenerateContentProvider(self.settings.gemini_api_key), self.settings.gemini_test_data_model
        return None

    def _fallback(self, run_id: str, *, attach_to_allure: bool, reason: str) -> GeneratedTestData:
        generated = GeneratedTestData(
            data=self.fallback_provider.generate(run_id),
            source=f"faker_fallback:{reason}",
            model=None,
            attempts=0,
            run_id=run_id,
        )
        self._attach(generated, attach_to_allure)
        return generated

    @staticmethod
    def _attach(generated: GeneratedTestData, attach_to_allure: bool) -> None:
        if not attach_to_allure:
            return
        attach_json("ai-test-data-used", generated.model_dump())


def stable_seed(run_id: str) -> int:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def build_prompt(run_id: str) -> str:
    return (
        "Generate coherent realistic Indonesian business test data for eDOT QA automation. "
        "Return only JSON matching the provided schema. "
        "Use safe dummy domains and phone numbers. "
        f"Make values unique for run_id {run_id}. "
        "Company must include legal_name, email, phone, street_address, industry. "
        "Customer must include name, contact, address. "
        "Do not include credentials, API keys, real private personal data, or extra fields."
    )


def business_test_data_json_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "company": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "legal_name": {
                        "type": "string",
                        "minLength": 5,
                        "maxLength": 120,
                        "description": "Indonesian legal company name starting with PT or CV.",
                    },
                    "email": {
                        "type": "string",
                        "minLength": 6,
                        "maxLength": 120,
                        "description": "Safe dummy email address.",
                    },
                    "phone": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 16,
                        "description": "Indonesian phone number in +62 format.",
                    },
                    "street_address": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 180,
                        "description": "Realistic Indonesian street address.",
                    },
                    "industry": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 60,
                        "description": "Business industry such as Retail or Distribution.",
                    },
                },
                "required": ["legal_name", "email", "phone", "street_address", "industry"],
            },
            "customer": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 100,
                        "description": "Indonesian customer name.",
                    },
                    "contact": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 120,
                        "description": "Indonesian phone number in +62 format, or safe dummy email.",
                    },
                    "address": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 180,
                        "description": "Realistic Indonesian customer address.",
                    },
                },
                "required": ["name", "contact", "address"],
            },
        },
        "required": ["company", "customer"],
    }


def gemini_response_schema(schema: dict) -> dict:
    cleaned: dict = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue
        if isinstance(value, dict):
            cleaned[key] = gemini_response_schema(value)
        elif isinstance(value, list):
            cleaned[key] = [gemini_response_schema(item) if isinstance(item, dict) else item for item in value]
        else:
            cleaned[key] = value
    return cleaned


def extract_gemini_text(body: dict) -> str:
    for candidate in body.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise RuntimeError("Gemini API returned no output text")


def generate_test_data(run_id: str | None = None, *, attach_to_allure: bool = True) -> GeneratedTestData:
    return TestDataGenerator().generate(run_id=run_id, attach_to_allure=attach_to_allure)
