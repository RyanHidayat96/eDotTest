from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from edot_qa.config import ROOT_DIR
from edot_qa.reporting.allure_helpers import allure_step, attach_json
from edot_qa.web.company_registration import CompanyRegistrationData
from edot_qa.web.company_user import CompanyUserData


DEFAULT_COMPANY_HANDOFF_PATH = ROOT_DIR / "artifacts" / "handoff" / "web_company.json"


def current_utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class CompanyHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: int = Field(default=2)
    company_name: str = Field(min_length=5, max_length=140)
    company_email: str = Field(min_length=6, max_length=120)
    company_code: str | None = Field(default=None, min_length=2, max_length=140)
    company_user_name: str | None = Field(default=None, min_length=3, max_length=100)
    company_user_username: str | None = Field(default=None, min_length=5, max_length=32)
    company_user_email: str | None = Field(default=None, min_length=6, max_length=120)
    source_run_id: str = Field(min_length=1, max_length=80)
    trial_days: int = Field(default=30, ge=1, le=60)
    created_at_utc: str = Field(default_factory=current_utc_timestamp)

    @classmethod
    def from_registration(
        cls,
        registration: CompanyRegistrationData,
        *,
        source_run_id: str,
        company_code: str | None = None,
        company_user: CompanyUserData | None = None,
    ) -> "CompanyHandoff":
        return cls(
            company_name=registration.company_name,
            company_email=registration.email,
            company_code=company_code,
            company_user_name=company_user.name if company_user else None,
            company_user_username=company_user.username if company_user else None,
            company_user_email=company_user.email if company_user else None,
            source_run_id=source_run_id,
        )

    @property
    def mobile_username(self) -> str:
        return self.company_user_username or self.company_email

    def as_mobile_environment(self) -> dict[str, str]:
        values = {"EWORK_EMAIL": self.mobile_username}
        if self.company_code:
            values["EWORK_COMPANY_CODE"] = self.company_code
        return values

    def as_safe_payload(self) -> dict[str, Any]:
        return self.model_dump()


def write_company_handoff(
    handoff: CompanyHandoff,
    path: str | Path = DEFAULT_COMPANY_HANDOFF_PATH,
    *,
    attach_to_allure: bool = True,
) -> Path:
    context = (
        allure_step(
            "Write web-to-mobile company handoff",
            data=handoff.as_safe_payload(),
            screenshot=False,
        )
        if attach_to_allure
        else nullcontext()
    )
    with context:
        resolved_path = Path(path)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(json.dumps(handoff.model_dump(), indent=2, sort_keys=True), encoding="utf-8")
        if attach_to_allure:
            attach_json("web-mobile-company-handoff", handoff.as_safe_payload())
        return resolved_path


def read_company_handoff(path: str | Path = DEFAULT_COMPANY_HANDOFF_PATH) -> CompanyHandoff | None:
    resolved_path = Path(path)
    if not resolved_path.is_file():
        return None
    return CompanyHandoff.model_validate(json.loads(resolved_path.read_text(encoding="utf-8")))


def delete_company_handoff(path: str | Path = DEFAULT_COMPANY_HANDOFF_PATH) -> None:
    resolved_path = Path(path)
    if resolved_path.is_file():
        resolved_path.unlink()
