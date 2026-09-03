from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://esuite.edot.id"
DEFAULT_STORAGE_STATE = ROOT_DIR / "artifacts" / "auth" / "esuite_storage_state.json"
DEFAULT_ALLURE_RESULTS = ROOT_DIR / "reports" / "allure-results"
DEFAULT_OPENAI_TEST_DATA_MODEL = "gpt-5-nano"


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


def _path_from_env(name: str, default: Path) -> Path:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    path = Path(raw_value)
    return path if path.is_absolute() else ROOT_DIR / path


@dataclass(frozen=True)
class Settings:
    esuite_base_url: str
    esuite_email: str | None
    esuite_password: str | None
    headless: bool
    slow_mo_ms: int
    browser: str
    storage_state_path: Path
    allure_results_dir: Path
    openai_api_key: str | None
    openai_test_data_model: str
    ai_test_data_max_attempts: int
    ai_test_data_max_output_tokens: int

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
            "OPENAI_API_KEY": "<set>" if self.openai_api_key else "<missing>",
            "OPENAI_TEST_DATA_MODEL": self.openai_test_data_model,
            "AI_TEST_DATA_MAX_ATTEMPTS": self.ai_test_data_max_attempts,
            "AI_TEST_DATA_MAX_OUTPUT_TOKENS": self.ai_test_data_max_output_tokens,
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
        storage_state_path=_path_from_env("PLAYWRIGHT_STORAGE_STATE", DEFAULT_STORAGE_STATE),
        allure_results_dir=_path_from_env("ALLURE_RESULTS_DIR", DEFAULT_ALLURE_RESULTS),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_test_data_model=os.getenv("OPENAI_TEST_DATA_MODEL", DEFAULT_OPENAI_TEST_DATA_MODEL),
        ai_test_data_max_attempts=_int_from_env("AI_TEST_DATA_MAX_ATTEMPTS", 2),
        ai_test_data_max_output_tokens=_int_from_env("AI_TEST_DATA_MAX_OUTPUT_TOKENS", 700),
    )
