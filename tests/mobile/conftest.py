from __future__ import annotations

import pytest

from edot_qa.mobile.config import MobileSettings, load_mobile_settings
from edot_qa.mobile.maestro import MaestroRunner
from edot_qa.reporting.allure_helpers import attach_json


@pytest.fixture(scope="session")
def mobile_settings() -> MobileSettings:
    settings = load_mobile_settings()
    settings.ensure_runtime_dirs()
    attach_json("mobile-runtime-settings", settings.as_safe_dict())
    return settings


@pytest.fixture()
def maestro_runner(mobile_settings: MobileSettings) -> MaestroRunner:
    return MaestroRunner(mobile_settings)
