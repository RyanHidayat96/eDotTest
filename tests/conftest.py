from __future__ import annotations

import pytest

from edot_qa.reporting.allure_helpers import attach_png


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
            attach_png(f"failure-screenshot-{report.when}", page.screenshot(full_page=True))
    except Exception as error:
        report.sections.append(("screenshot attachment failed", str(error)))
