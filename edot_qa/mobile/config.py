from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from edot_qa.config import DEFAULT_ALLURE_RESULTS, ROOT_DIR
from edot_qa.handoff import DEFAULT_COMPANY_HANDOFF_PATH, read_company_handoff
from edot_qa.mobile.flow_profile import DELIBERATE_WRONG_PASSWORD_FIELD_ID, EWORK_FLOW_VARIABLES


try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


DEFAULT_MAESTRO_FLOW_DIR = ROOT_DIR / "mobile" / "flows"
DEFAULT_EWORK_STORAGE_STATE = ROOT_DIR / "artifacts" / "auth" / "ework_session_state.json"
DEFAULT_EWORK_APP_ID = "id.edot.ework"


@dataclass(frozen=True)
class MobileSettings:
    maestro_cli: str
    adb_command: str
    mobile_device_id: str | None
    mobile_flow_timeout_seconds: int
    edot_live: bool
    prefer_company_handoff: bool
    ework_app_id: str
    ework_email: str | None = field(repr=False)
    ework_password: str | None = field(repr=False)
    ework_company_code: str | None
    maestro_flow_dir: Path = DEFAULT_MAESTRO_FLOW_DIR
    allure_results_dir: Path = DEFAULT_ALLURE_RESULTS
    company_handoff_path: Path = DEFAULT_COMPANY_HANDOFF_PATH
    ework_storage_state_path: Path = DEFAULT_EWORK_STORAGE_STATE

    @property
    def has_ework_credentials(self) -> bool:
        return bool(self.ework_email and self.ework_password)

    def missing_login_requirements(self) -> list[str]:
        requirements = {
            "EWORK_APP_ID": self.ework_app_id,
            "EWORK_COMPANY_CODE": self.ework_company_code,
            "EWORK_EMAIL": self.ework_email,
            "EWORK_PASSWORD": self.ework_password,
        }
        return [key for key, value in requirements.items() if not value]

    def missing_customer_requirements(self) -> list[str]:
        # Customer creation resumes a stored session; it does not re-enter login credentials.
        return ["EWORK_APP_ID"] if not self.ework_app_id else []

    def ensure_runtime_dirs(self) -> None:
        self.allure_results_dir.mkdir(parents=True, exist_ok=True)

    def as_safe_dict(self) -> dict[str, str]:
        return {
            "MAESTRO_CLI": self.maestro_cli,
            "ADB_COMMAND": self.adb_command,
            "MOBILE_DEVICE_ID": self.mobile_device_id or "<auto>",
            "MOBILE_FLOW_TIMEOUT_SECONDS": str(self.mobile_flow_timeout_seconds),
            "EDOT_LIVE": str(self.edot_live).lower(),
            "EWORK_HANDOFF_MODE": str(self.prefer_company_handoff).lower(),
            "EWORK_APP_ID": self.ework_app_id,
            "EWORK_EMAIL": "<set>" if self.ework_email else "<missing>",
            "EWORK_PASSWORD": "<set>" if self.ework_password else "<missing>",
            "EWORK_COMPANY_CODE": "<set>" if self.ework_company_code else "<missing>",
            "EWORK_UI_PROFILE": "versioned-default",
            "MAESTRO_FLOW_DIR": str(self.maestro_flow_dir),
            "ALLURE_RESULTS_DIR": str(self.allure_results_dir),
            "EWORK_COMPANY_HANDOFF_PATH": str(self.company_handoff_path),
            "EWORK_STORAGE_STATE": str(self.ework_storage_state_path),
        }

    def maestro_environment(self, extra_values: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env.update(self.maestro_variables(extra_values))
        return env

    def deliberate_wrong_password_field_override(self) -> dict[str, str]:
        return {"EWORK_PASSWORD_FIELD_ID": DELIBERATE_WRONG_PASSWORD_FIELD_ID}

    def maestro_variables(self, extra_values: dict[str, str] | None = None) -> dict[str, str]:
        variables = {
            **EWORK_FLOW_VARIABLES,
            "EWORK_APP_ID": self.ework_app_id,
        }
        for key, value in {
            "EWORK_EMAIL": self.ework_email,
            "EWORK_PASSWORD": self.ework_password,
            "EWORK_COMPANY_CODE": self.ework_company_code,
        }.items():
            if value:
                variables[key] = value
        for key, value in (extra_values or {}).items():
            if value:
                variables[key] = value
        return variables


def load_mobile_settings(
    *,
    prefer_handoff: bool = False,
    company_handoff_path: Path | None = None,
) -> MobileSettings:
    _load_dotenv()
    handoff_path = company_handoff_path or DEFAULT_COMPANY_HANDOFF_PATH
    handoff = read_company_handoff(handoff_path) if prefer_handoff else None
    handoff_username = handoff.mobile_username if handoff else None
    handoff_code = handoff.company_code if handoff else None
    return MobileSettings(
        maestro_cli=os.getenv("MAESTRO_CLI") or "maestro",
        adb_command=os.getenv("ADB_COMMAND") or "adb",
        mobile_device_id=os.getenv("MOBILE_DEVICE_ID") or None,
        mobile_flow_timeout_seconds=_int_from_env("MOBILE_FLOW_TIMEOUT_SECONDS", 300),
        edot_live=_bool_from_env("EDOT_LIVE"),
        prefer_company_handoff=prefer_handoff,
        ework_app_id=os.getenv("EWORK_APP_ID") or DEFAULT_EWORK_APP_ID,
        ework_email=_identity_value(os.getenv("EWORK_EMAIL"), handoff_username, prefer_handoff),
        ework_password=os.getenv("EWORK_PASSWORD") or None,
        ework_company_code=_identity_value(os.getenv("EWORK_COMPANY_CODE"), handoff_code, prefer_handoff),
        company_handoff_path=handoff_path,
    )


def _load_dotenv() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def _identity_value(env_value: str | None, handoff_value: str | None, prefer_handoff: bool) -> str | None:
    if prefer_handoff and handoff_value:
        return handoff_value
    return env_value or None


def _bool_from_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _int_from_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)
