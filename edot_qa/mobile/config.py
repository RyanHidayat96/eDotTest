from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from edot_qa.config import DEFAULT_ALLURE_RESULTS, ROOT_DIR


try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


DEFAULT_MAESTRO_FLOW_DIR = ROOT_DIR / "mobile" / "flows"
DEFAULT_MAESTRO_OUTPUT_DIR = ROOT_DIR / "artifacts" / "maestro"


@dataclass(frozen=True)
class MobileSettings:
    maestro_cli: str
    adb_command: str
    mobile_device_id: str | None
    ework_app_id: str | None
    ework_email: str | None
    ework_password: str | None
    ework_company_code: str | None
    maestro_flow_dir: Path
    maestro_output_dir: Path
    allure_results_dir: Path

    @property
    def has_ework_credentials(self) -> bool:
        return bool(self.ework_email and self.ework_password)

    @property
    def has_app_id(self) -> bool:
        return bool(self.ework_app_id)

    def ensure_runtime_dirs(self) -> None:
        self.maestro_output_dir.mkdir(parents=True, exist_ok=True)
        self.allure_results_dir.mkdir(parents=True, exist_ok=True)

    def as_safe_dict(self) -> dict[str, str]:
        return {
            "MAESTRO_CLI": self.maestro_cli,
            "ADB_COMMAND": self.adb_command,
            "MOBILE_DEVICE_ID": self.mobile_device_id or "<auto>",
            "EWORK_APP_ID": self.ework_app_id or "<missing>",
            "EWORK_EMAIL": "<set>" if self.ework_email else "<missing>",
            "EWORK_PASSWORD": "<set>" if self.ework_password else "<missing>",
            "EWORK_COMPANY_CODE": "<set>" if self.ework_company_code else "<missing>",
            "MAESTRO_FLOW_DIR": str(self.maestro_flow_dir),
            "MAESTRO_OUTPUT_DIR": str(self.maestro_output_dir),
            "ALLURE_RESULTS_DIR": str(self.allure_results_dir),
        }

    def maestro_environment(self) -> dict[str, str]:
        env = os.environ.copy()
        optional_values = {
            "EWORK_APP_ID": self.ework_app_id,
            "EWORK_EMAIL": self.ework_email,
            "EWORK_PASSWORD": self.ework_password,
            "EWORK_COMPANY_CODE": self.ework_company_code,
        }
        for key, value in optional_values.items():
            if value:
                env[key] = value
        return env


def load_mobile_settings() -> MobileSettings:
    _load_dotenv()
    return MobileSettings(
        maestro_cli=os.getenv("MAESTRO_CLI", "maestro"),
        adb_command=os.getenv("ADB_COMMAND", "adb"),
        mobile_device_id=os.getenv("MOBILE_DEVICE_ID") or None,
        ework_app_id=os.getenv("EWORK_APP_ID") or None,
        ework_email=os.getenv("EWORK_EMAIL") or None,
        ework_password=os.getenv("EWORK_PASSWORD") or None,
        ework_company_code=os.getenv("EWORK_COMPANY_CODE") or None,
        maestro_flow_dir=_path_from_env("MAESTRO_FLOW_DIR", DEFAULT_MAESTRO_FLOW_DIR),
        maestro_output_dir=_path_from_env("MAESTRO_OUTPUT_DIR", DEFAULT_MAESTRO_OUTPUT_DIR),
        allure_results_dir=_path_from_env("ALLURE_RESULTS_DIR", DEFAULT_ALLURE_RESULTS),
    )


def _load_dotenv() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def _path_from_env(name: str, default: Path) -> Path:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    path = Path(raw_value)
    return path if path.is_absolute() else ROOT_DIR / path
