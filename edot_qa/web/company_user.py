from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from edot_qa.ai.test_data import GeneratedTestData


USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{4,31}$")


class CompanyUserData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=100)
    username: str = Field(min_length=5, max_length=32)
    employee_id: str = Field(min_length=3, max_length=32)
    email: str = Field(min_length=6, max_length=120)
    phone: str = Field(min_length=10, max_length=13)
    password: str = Field(min_length=6, max_length=120)
    status: str = Field(default="Active")
    branch_name: str = Field(default="Main", min_length=2, max_length=60)

    @field_validator("username")
    @classmethod
    def username_must_be_mobile_safe(cls, value: str) -> str:
        if not USERNAME_RE.match(value):
            raise ValueError("username must start with a letter and contain only letters, numbers, dots, hyphens, or underscores")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_be_local_indonesian_number(cls, value: str) -> str:
        digits = re.sub(r"\D+", "", value)
        if digits.startswith("62"):
            digits = digits[2:]
        if digits.startswith("0"):
            digits = digits[1:]
        if len(digits) < 10 or len(digits) > 13:
            raise ValueError("phone must be an Indonesian local number without +62")
        return digits

    @classmethod
    def from_generated_test_data(cls, generated: GeneratedTestData, *, password: str) -> "CompanyUserData":
        suffix = generated.run_id[-8:].lower()
        digits = _stable_digits(generated.run_id, length=9)
        return cls(
            name=f"QA User {suffix.upper()}",
            username=f"qauser{suffix}",
            employee_id=f"EMP{suffix.upper()}",
            email=f"qauser{suffix}@gmail.com",
            phone=f"812{digits}",
            password=password,
        )

    def as_allure_payload(self) -> dict[str, Any]:
        return self.model_dump()

    def as_handoff_payload(self) -> dict[str, str]:
        return {
            "company_user_name": self.name,
            "company_user_username": self.username,
            "company_user_email": self.email,
        }


def _stable_digits(value: str, *, length: int) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    digits = "".join(str(int(char, 16) % 10) for char in digest)
    return digits[:length].ljust(length, "0")
