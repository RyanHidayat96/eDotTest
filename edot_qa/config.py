from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://esuite.edot.id"
DEFAULT_STORAGE_STATE = ROOT_DIR / "artifacts" / "auth" / "esuite_storage_state.json"
DEFAULT_ALLURE_RESULTS = ROOT_DIR / "reports" / "allure-results"
DEFAULT_TRIAGE_REPORT = ROOT_DIR / "reports" / "triage" / "triage-report.md"
DEFAULT_GEMINI_TEST_DATA_MODEL = "gemini-3.1-flash-lite"
DEFAULT_GEMINI_TRIAGE_MODEL = "gemini-3.1-flash-lite"
DEFAULT_AI_TEST_DATA_MAX_ATTEMPTS = 2
DEFAULT_AI_TEST_DATA_MAX_OUTPUT_TOKENS = 700
DEFAULT_AI_TRIAGE_MAX_OUTPUT_TOKENS = 900


def _load_dotenv() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def _bool_from_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    return int(raw_value)


@dataclass(frozen=True)
class Settings:
    esuite_base_url: str
    esuite_email: str | None = field(repr=False)
    esuite_password: str | None = field(repr=False)
    headless: bool
    slow_mo_ms: int
    browser: str
    storage_state_path: Path
    allure_results_dir: Path
    triage_report_path: Path
    gemini_api_key: str | None
    gemini_test_data_model: str
    gemini_triage_model: str
    ai_test_data_max_attempts: int
    ai_test_data_max_output_tokens: int
    ai_triage_max_output_tokens: int

    @property
    def has_esuite_credentials(self) -> bool:
        return bool(self.esuite_email and self.esuite_password)

    def ensure_runtime_dirs(self) -> None:
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.allure_results_dir.mkdir(parents=True, exist_ok=True)

    def as_safe_dict(self) -> dict[str, str | bool | int]:
        return {
            "ESUITE_BASE_URL": self.esuite_base_url,
            "ESUITE_EMAIL": "<set>" if self.esuite_email else "<missing>",
            "ESUITE_PASSWORD": "<set>" if self.esuite_password else "<missing>",
            "HEADLESS": self.headless,
            "SLOW_MO_MS": self.slow_mo_ms,
            "BROWSER": self.browser,
            "PLAYWRIGHT_STORAGE_STATE": str(self.storage_state_path),
            "ALLURE_RESULTS_DIR": str(self.allure_results_dir),
            "TRIAGE_REPORT_PATH": str(self.triage_report_path),
            "GEMINI_API_KEY": "<set>" if self.gemini_api_key else "<missing>",
            "GEMINI_TEST_DATA_MODEL": self.gemini_test_data_model,
            "GEMINI_TRIAGE_MODEL": self.gemini_triage_model,
            "AI_TEST_DATA_MAX_ATTEMPTS": self.ai_test_data_max_attempts,
            "AI_TEST_DATA_MAX_OUTPUT_TOKENS": self.ai_test_data_max_output_tokens,
            "AI_TRIAGE_MAX_OUTPUT_TOKENS": self.ai_triage_max_output_tokens,
        }


def load_settings() -> Settings:
    _load_dotenv()
    return Settings(
        esuite_base_url=os.getenv("ESUITE_BASE_URL", DEFAULT_BASE_URL),
        esuite_email=os.getenv("ESUITE_EMAIL") or None,
        esuite_password=os.getenv("ESUITE_PASSWORD") or None,
        headless=_bool_from_env("HEADLESS", True),
        slow_mo_ms=_int_from_env("SLOW_MO_MS", 0),
        browser=os.getenv("BROWSER", "chromium"),
        storage_state_path=DEFAULT_STORAGE_STATE,
        allure_results_dir=DEFAULT_ALLURE_RESULTS,
        triage_report_path=DEFAULT_TRIAGE_REPORT,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_test_data_model=os.getenv("GEMINI_TEST_DATA_MODEL", DEFAULT_GEMINI_TEST_DATA_MODEL),
        gemini_triage_model=DEFAULT_GEMINI_TRIAGE_MODEL,
        ai_test_data_max_attempts=DEFAULT_AI_TEST_DATA_MAX_ATTEMPTS,
        ai_test_data_max_output_tokens=DEFAULT_AI_TEST_DATA_MAX_OUTPUT_TOKENS,
        ai_triage_max_output_tokens=DEFAULT_AI_TRIAGE_MAX_OUTPUT_TOKENS,
    )
