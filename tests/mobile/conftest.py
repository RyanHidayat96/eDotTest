from __future__ import annotations

from typing import Callable, TypeVar

import pytest

from edot_qa.mobile.config import MobileSettings, load_mobile_settings
from edot_qa.mobile.maestro import MaestroResult, MaestroRunner, assert_maestro_passed
from edot_qa.mobile.runtime import MobilePrerequisiteError
from edot_qa.reporting.allure_helpers import attach_json


T = TypeVar("T")


@pytest.fixture(scope="session")
def mobile_settings() -> MobileSettings:
    settings = load_mobile_settings()
    settings.ensure_runtime_dirs()
    attach_json("mobile-runtime-settings", settings.as_safe_dict())
    return settings


@pytest.fixture()
def maestro_runner(mobile_settings: MobileSettings) -> MaestroRunner:
    return MaestroRunner(mobile_settings)


@pytest.fixture()
def run_maestro_flow(maestro_runner: MaestroRunner):
    def _run(
        flow: str,
        *,
        timeout_seconds: int | None = None,
        extra_env: dict[str, str] | None = None,
        step_title: str | None = None,
        expected: str | None = None,
    ) -> MaestroResult:
        return assert_maestro_passed(
            maestro_runner.run_flow(
                flow,
                timeout_seconds=timeout_seconds or maestro_runner.settings.mobile_flow_timeout_seconds,
                extra_env=extra_env,
                step_title=step_title,
                expected=expected,
            )
        )

    return _run


@pytest.fixture()
def run_mobile_scenario(mobile_settings: MobileSettings) -> Callable[[Callable[[], T]], T]:
    def _run(action: Callable[[], T]) -> T:
        try:
            return action()
        except MobilePrerequisiteError as error:
            if mobile_settings.edot_live:
                pytest.fail(str(error))
            pytest.skip(str(error))

    return _run
