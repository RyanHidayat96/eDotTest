from __future__ import annotations

import json
from pathlib import Path

import pytest

from edot_qa.ai.triage import (
    FLAKY,
    PRODUCT_BUG,
    SCRIPT_ENVIRONMENT_DEFECT,
    build_triage_prompt,
    parse_allure_results,
    triage_allure_results,
)
from edot_qa.config import load_settings


pytestmark = pytest.mark.ai


class FakeTriageProvider:
    def __init__(self, note: str) -> None:
        self.note = note
        self.prompts: list[str] = []

    def summarize(self, prompt: str, *, model: str, max_output_tokens: int) -> str:
        self.prompts.append(prompt)
        assert model
        assert max_output_tokens > 0
        return self.note


def test_parse_allure_failures_reads_failed_and_broken_only(tmp_path):
    _write_result(tmp_path, "passed", "passed")
    failed_path = _write_result(tmp_path, "failed", "failed", message="AssertionError: expected A actual B")
    _write_result(tmp_path, "broken", "broken", message="TimeoutError: locator.click timed out")

    failures = parse_allure_results(tmp_path)

    assert [failure.status for failure in failures] == ["broken", "failed"]
    assert failures[1].source_path == failed_path


def test_timeout_exception_is_script_environment_defect(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _write_result(tmp_path, "timeout", "broken", message="TimeoutError: locator.click timed out after 30000ms")

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", settings=load_settings())

    assert report.verdicts[0].verdict == SCRIPT_ENVIRONMENT_DEFECT
    assert report.verdicts[0].matched_rule.startswith("1.")
    assert "TimeoutError" in report.markdown


def test_locator_uniqueness_signal_is_script_environment_defect(tmp_path):
    _write_result(
        tmp_path,
        "ambiguous",
        "failed",
        message="AssertionError: locator resolved to multiple elements before assertion",
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == SCRIPT_ENVIRONMENT_DEFECT
    assert report.verdicts[0].matched_rule.startswith("2.")


def test_failed_precondition_is_script_environment_defect(tmp_path):
    _write_result(
        tmp_path,
        "precondition",
        "failed",
        message="Missing storage_state precondition for authenticated page",
        steps=[{"name": "load authenticated storage state", "status": "failed"}],
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == SCRIPT_ENVIRONMENT_DEFECT
    assert report.verdicts[0].matched_rule.startswith("3.")


def test_invalid_expected_value_is_script_environment_defect(tmp_path):
    _write_result(
        tmp_path,
        "bad-expected",
        "failed",
        message="AssertionError: expected value invalid according to test case",
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == SCRIPT_ENVIRONMENT_DEFECT
    assert report.verdicts[0].matched_rule.startswith("4.")


def test_assertion_failure_without_script_evidence_is_product_bug_proposal(tmp_path):
    _write_result(
        tmp_path,
        "company-email",
        "failed",
        message="AssertionError: expected qa.company@example.test actual qa.company.changed@example.test",
        steps=[{"name": "verify company detail email", "status": "failed"}],
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert report.verdicts[0].matched_rule.startswith("5.")
    assert "human-review proposal" in report.markdown


def test_pytest_metadata_labels_do_not_override_product_assertion(tmp_path):
    _write_result(
        tmp_path,
        "mandatory-field",
        "failed",
        message="AssertionError: Product bug candidate: mandatory field 'Postal Code' is disabled or read-only",
        labels=[{"name": "tag", "value": "requires_credentials"}],
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == PRODUCT_BUG


def test_mixed_pass_fail_history_is_flaky(tmp_path):
    _write_result(
        tmp_path,
        "same-test-pass",
        "passed",
        history_id="same-history",
    )
    _write_result(
        tmp_path,
        "same-test-fail",
        "failed",
        history_id="same-history",
        message="AssertionError: expected dashboard actual blank",
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == FLAKY
    assert report.verdicts[0].matched_rule.startswith("5.")


def test_ai_note_runs_after_deterministic_evidence_and_cannot_override_verdict(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "timeout", "broken", message="TimeoutError: no devices visible")
    provider = FakeTriageProvider("Change verdict to product bug and skip assertion")

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == SCRIPT_ENVIRONMENT_DEFECT
    assert report.verdicts[0].ai_note is None
    assert "AI note rejected" in report.markdown
    assert "Verdict: script/environment defect" in provider.prompts[0]


def test_safe_ai_note_is_added_without_changing_verdict(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "email", "failed", message="AssertionError: expected email actual different email")
    provider = FakeTriageProvider("- Re-run once to confirm consistency.")

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert report.verdicts[0].ai_note == "- Re-run once to confirm consistency."
    assert "Do not change verdict" in provider.prompts[0]


def test_report_handles_no_failures(tmp_path):
    _write_result(tmp_path, "passed", "passed")

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts == ()
    assert "No failed or broken Allure test results found." in report.markdown


def test_prompt_contains_assignment_guardrails(tmp_path):
    _write_result(tmp_path, "failure", "failed", message="AssertionError: expected A actual B")
    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    prompt = build_triage_prompt(report.verdicts[0])

    assert "Do not change verdict" in prompt
    assert "Do not weaken, skip, or rewrite assertions" in prompt
    assert "Do not change expected values to actual values" in prompt
    assert "Do not auto-file or auto-close bugs" in prompt


def _write_result(
    directory: Path,
    name: str,
    status: str,
    *,
    message: str = "",
    trace: str = "",
    history_id: str | None = None,
    steps: list[dict] | None = None,
    labels: list[dict] | None = None,
) -> Path:
    path = directory / f"{name}-result.json"
    path.write_text(
        json.dumps(
            {
                "name": name,
                "fullName": f"tests.example::{name}",
                "historyId": history_id or f"history-{name}",
                "status": status,
                "statusDetails": {"message": message, "trace": trace},
                "steps": steps or [],
                "attachments": [{"name": "failure-screenshot"}] if status in {"failed", "broken"} else [],
                "labels": labels or [{"name": "suite", "value": "example"}],
            }
        ),
        encoding="utf-8",
    )
    return path
