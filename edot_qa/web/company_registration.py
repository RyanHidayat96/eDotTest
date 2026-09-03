from __future__ import annotations

import os
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

    @classmethod
    def from_env(cls) -> "LocationCascade":
        return cls(
            country=os.getenv("ESUITE_COMPANY_COUNTRY", cls.model_fields["country"].default),
            province=os.getenv("ESUITE_COMPANY_PROVINCE", cls.model_fields["province"].default),
            city=os.getenv("ESUITE_COMPANY_CITY", cls.model_fields["city"].default),
            district=os.getenv("ESUITE_COMPANY_DISTRICT", cls.model_fields["district"].default),
            zone=os.getenv("ESUITE_COMPANY_ZONE", cls.model_fields["zone"].default),
            postal_code=os.getenv("ESUITE_COMPANY_POSTAL_CODE", cls.model_fields["postal_code"].default),
        )


class CompanyRegistrationData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(min_length=5, max_length=140)
    email: str = Field(min_length=6, max_length=120)
    phone: str = Field(min_length=10, max_length=16)
    industry_type: str = Field(min_length=3, max_length=60)
    company_type: str = Field(default="Retailer", min_length=2, max_length=60)
    language: str = Field(default="English", min_length=2, max_length=60)
    street_address: str = Field(min_length=10, max_length=180)
    location: LocationCascade = Field(default_factory=LocationCascade.from_env)

    @classmethod
    def from_generated_test_data(cls, generated: GeneratedTestData) -> "CompanyRegistrationData":
        company = generated.data.company
        suffix = generated.run_id[-8:].upper()
        company_name = normalize_company_name_for_web(company.legal_name, suffix)
        if suffix not in company_name.upper():
            company_name = f"{company_name} QA {suffix}"
        return cls(
            company_name=company_name,
            email=company.email,
            phone=normalize_phone_for_web(company.phone),
            industry_type=normalize_industry_for_web(company.industry),
            company_type=os.getenv("ESUITE_COMPANY_TYPE", cls.model_fields["company_type"].default),
            language=os.getenv("ESUITE_COMPANY_LANGUAGE", cls.model_fields["language"].default),
            street_address=company.street_address,
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
    return digits[:13]


def normalize_industry_for_web(industry: str) -> str:
    lowered = industry.strip().lower()
    if "food" in lowered or "beverage" in lowered:
        return "Food & Beverage"
    if "manufact" in lowered:
        return "Manufacturing"
    if "transport" in lowered or "logistic" in lowered or "distribut" in lowered:
        return "Transportation and Logistics"
    if "tech" in lowered:
        return "Technology"
    return "Retail"
