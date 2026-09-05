from __future__ import annotations

import os

import pytest

from edot_qa.reporting.allure_metadata import apply_allure_metadata
from edot_qa.reporting.allure_helpers import attach_page_evidence


DELIBERATE_FAILURE_ENV = "EDOT_DELIBERATE_FAILURE"
DELIBERATE_FAILURE_MODE = "wrong_locator"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    deliberate_enabled = os.getenv(DELIBERATE_FAILURE_ENV, "").strip().lower() == DELIBERATE_FAILURE_MODE
    if deliberate_enabled:
        return

    kept = []
    deselected = []
    for item in items:
        if item.get_closest_marker("deliberate_failure"):
            deselected.append(item)
        else:
            kept.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


@pytest.fixture(autouse=True)
def allure_metadata(request: pytest.FixtureRequest) -> None:
    apply_allure_metadata(request.node)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
    if not report.failed:
        return

    page = item.funcargs.get("page") or item.funcargs.get("authenticated_page")
    if page is None:
        return

    try:
        if not page.is_closed():
            attach_page_evidence(f"failure-evidence-{report.when}", page, full_page=True)
    except Exception as error:
        report.sections.append(("screenshot attachment failed", str(error)))
