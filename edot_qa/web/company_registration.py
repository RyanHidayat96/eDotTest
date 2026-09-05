from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from edot_qa.ai.test_data import GeneratedTestData


UNSAFE_COMPANY_NAME = re.compile(r"[^A-Za-z0-9 ]+")


class LocationCascade(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    country: str = Field(default="Indonesia", min_length=2)
    province: str = Field(default="DKI Jakarta", min_length=2)
    city: str = Field(default="Jakarta Selatan", min_length=2)
    district: str = Field(default="Kebayoran Baru", min_length=2)
    zone: str = Field(default="Senayan", min_length=2)
    postal_code: str = Field(default="12190", min_length=3)

class CompanyRegistrationData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(min_length=5, max_length=140)
    email: str = Field(min_length=6, max_length=120)
    phone: str = Field(min_length=10, max_length=16)
    industry_type: str = Field(default="Retail", min_length=3, max_length=60)
    company_type: str = Field(default="Retailer", min_length=2, max_length=60)
    language: str = Field(default="English", min_length=2, max_length=60)
    street_address: str = Field(min_length=10, max_length=180)
    branch_name: str = Field(default="Main", min_length=2, max_length=60)
    location: LocationCascade = Field(default_factory=LocationCascade)

    @classmethod
    def from_generated_test_data(cls, generated: GeneratedTestData) -> "CompanyRegistrationData":
        company = generated.data.company
        suffix = generated.run_id[-8:].upper()
        company_name = normalize_company_name_for_web(company.legal_name, suffix)
        if suffix not in company_name.upper():
            company_name = f"{company_name} QA {suffix}"
        return cls(
            company_name=company_name,
            email=normalize_email_for_web(company.email, suffix),
            phone=normalize_phone_for_web(company.phone),
            industry_type=cls.model_fields["industry_type"].default,
            company_type=cls.model_fields["company_type"].default,
            language=cls.model_fields["language"].default,
            street_address=normalize_street_address_for_web(company.street_address),
            branch_name=cls.model_fields["branch_name"].default,
        )

    def as_allure_payload(self) -> dict[str, Any]:
        return self.model_dump()

    def expected_detail_values(self) -> dict[str, str]:
        return {
            "name": self.company_name,
            "industry type": self.industry_type,
            "company type": self.company_type,
            "address": self.street_address,
            "postal code": self.location.postal_code,
            "email": self.email,
            "phone": self.phone,
        }


def normalize_company_name_for_web(company_name: str, suffix: str) -> str:
    cleaned = UNSAFE_COMPANY_NAME.sub(" ", company_name)
    words = cleaned.split()
    if not words:
        return f"PT Nusantara Ritel Mandiri QA {suffix}"
    prefix = words[0].upper()
    if prefix not in {"PT", "CV"}:
        words.insert(0, "PT")
    root_words: list[str] = []
    for word in words[1:]:
        upper_word = word.upper()
        if upper_word in {"PT", "CV", "PERSERO", "TBK", "QA", suffix.upper()}:
            continue
        root_words.append(word.title())
    root = root_words[0] if root_words else "Ritel"
    return f"{words[0].upper()} {root} QA {suffix}"


def normalize_phone_for_web(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone)
    if digits.startswith("62"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not digits:
        return "8123456789"
    if not digits.startswith("8"):
        digits = f"8{digits}"
    if len(digits) < 10:
        digits = digits.ljust(10, "0")
    return digits[:13]


def normalize_email_for_web(email: str, suffix: str) -> str:
    cleaned = email.strip().lower()
    local_part = cleaned.split("@", 1)[0]
    if cleaned.endswith(".dummy") or not cleaned.endswith((".test", ".com", ".co.id", ".id")):
        return f"{local_part[:12] or 'qa'}{suffix.lower()}@example.test"
    if len(cleaned) <= 30:
        return cleaned
    return f"qa{suffix.lower()}@qa.test"


def normalize_street_address_for_web(address: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", address)
    words = cleaned.split()
    if not words:
        return "Jalan Sudirman Jakarta"
    normalized = " ".join(words[:6])
    if len(normalized) < 10:
        normalized = f"{normalized} Jakarta".strip()
    return normalized[:80]
