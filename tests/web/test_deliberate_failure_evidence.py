from __future__ import annotations

import pytest

from edot_qa.web.pages.deliberate_failure_page import DeliberateFailurePage
from tools.evidence_workflow import (
    DELIBERATE_FAILURE_ENV,
    DELIBERATE_FAILURE_MODE,
    deliberate_failure_enabled,
)


pytestmark = pytest.mark.web


def test_deliberate_failure_toggle_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DELIBERATE_FAILURE_ENV, raising=False)

    assert deliberate_failure_enabled() is False


def test_deliberate_failure_toggle_requires_wrong_locator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DELIBERATE_FAILURE_ENV, "other")

    assert deliberate_failure_enabled() is False

    monkeypatch.setenv(DELIBERATE_FAILURE_ENV, DELIBERATE_FAILURE_MODE)
    assert deliberate_failure_enabled() is True


@pytest.mark.deliberate_failure
@pytest.mark.skipif(
    not deliberate_failure_enabled(),
    reason=f"set {DELIBERATE_FAILURE_ENV}={DELIBERATE_FAILURE_MODE} for deliberate evidence",
)
def test_deliberate_wrong_locator_failure_records_real_allure_failure(page) -> None:
    page_object = DeliberateFailurePage(page)
    page_object.open_fixture_page()
    page_object.expect_missing_submit_locator_visible()
