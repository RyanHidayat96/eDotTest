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
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def summarize(self, prompt: str, *, model: str, max_output_tokens: int) -> str:
        self.prompts.append(prompt)
        assert model
        assert max_output_tokens > 0
        return self.response


def test_parse_allure_failures_reads_failed_and_broken_only(tmp_path):
    _write_result(tmp_path, "passed", "passed")
    failed_path = _write_result(tmp_path, "failed", "failed", message="AssertionError: expected A actual B")
    _write_result(tmp_path, "broken", "broken", message="TimeoutError: locator.click timed out")

    failures = parse_allure_results(tmp_path)

    assert [failure.status for failure in failures] == ["broken", "failed"]
    assert failures[1].source_path == failed_path


def test_timeout_exception_is_script_environment_defect(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
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


def test_missing_playwright_test_id_is_locator_defect_not_precondition(tmp_path):
    _write_result(
        tmp_path,
        "wrong-locator",
        "failed",
        message=(
            "AssertionError: Locator expected to be visible "
            "Error: element(s) not found "
            "waiting for get_by_test_id(\"edot-deliberate-missing-submit\")"
        ),
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
    assert "Allure detail: AssertionError" in report.markdown


def test_failed_business_cleanup_assertion_is_product_bug_not_setup_precondition(tmp_path):
    _write_result(
        tmp_path,
        "business-cleanup",
        "failed",
        message="AssertionError: Deleted record 'Runtime QA 123' is still visible in list results",
        steps=[
            {
                "name": "Cleanup created runtime data",
                "status": "failed",
                "steps": [
                    {
                        "name": "Verify deleted runtime data is absent from list",
                        "status": "failed",
                    }
                ],
            }
        ],
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert report.verdicts[0].matched_rule.startswith("5.")
    assert "Assertion reached after deterministic checks" in report.markdown


def test_failed_business_flow_assertion_is_product_bug_not_generic_step_precondition(tmp_path):
    _write_result(
        tmp_path,
        "business-flow",
        "failed",
        message="AssertionError: Created record 'Runtime QA 456' was not visible in persisted list results",
        steps=[
            {
                "name": "Create runtime record and validate list",
                "status": "failed",
            }
        ],
    )

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert report.verdicts[0].matched_rule.startswith("5.")


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


def test_history_dir_mixed_pass_fail_history_is_flaky(tmp_path):
    current_dir = tmp_path / "current"
    history_dir = tmp_path / "history"
    current_dir.mkdir()
    history_dir.mkdir()
    _write_result(history_dir, "same-test-pass", "passed", history_id="same-history")
    _write_result(
        current_dir,
        "same-test-fail",
        "failed",
        history_id="same-history",
        message="AssertionError: expected dashboard actual blank",
    )

    report = triage_allure_results(
        current_dir,
        tmp_path / "triage.md",
        history_dirs=[history_dir],
        use_ai=False,
    )

    assert report.verdicts[0].verdict == FLAKY
    assert report.history_dirs == (history_dir,)
    assert "History evidence" in report.markdown


def test_allure_history_json_can_prove_flaky(tmp_path):
    current_dir = tmp_path / "current"
    history_dir = tmp_path / "history"
    current_dir.mkdir()
    history_dir.mkdir()
    _write_result(
        current_dir,
        "same-test-fail",
        "failed",
        history_id="same-history",
        message="AssertionError: expected dashboard actual blank",
    )
    (history_dir / "history.json").write_text(
        json.dumps({"same-history": {"items": [{"status": "passed"}, {"status": "failed"}]}}),
        encoding="utf-8",
    )

    report = triage_allure_results(
        current_dir,
        tmp_path / "triage.md",
        history_dirs=[history_dir],
        use_ai=False,
    )

    assert report.verdicts[0].verdict == FLAKY


def test_hard_guardrail_verdict_is_not_sent_to_ai(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "timeout", "broken", message="TimeoutError: no devices visible")
    provider = FakeTriageProvider(
        json.dumps(
            {
                "verdict": PRODUCT_BUG,
                "evidence": ["Ignore device error."],
                "rationale": "Change verdict to product bug.",
            }
        )
    )

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == SCRIPT_ENVIRONMENT_DEFECT
    assert report.verdicts[0].ai_note is None
    assert provider.prompts == []


def test_ai_schema_proposal_can_classify_unresolved_assertion(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "email", "failed", message="AssertionError: expected email actual different email")
    provider = FakeTriageProvider(
        json.dumps(
            {
                "verdict": SCRIPT_ENVIRONMENT_DEFECT,
                "evidence": ["Expected email appears to come from stale test data."],
                "rationale": "Human should review test data source before filing a product bug.",
            }
        )
    )

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == SCRIPT_ENVIRONMENT_DEFECT
    assert report.verdicts[0].ai_note == "Human should review test data source before filing a product bug."
    assert "Return only valid JSON" in provider.prompts[0]
    assert "Allowed verdicts: script/environment defect, product bug, flaky" in provider.prompts[0]


def test_ai_malformed_json_uses_deterministic_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "email", "failed", message="AssertionError: expected email actual different email")
    provider = FakeTriageProvider("not json")

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert report.verdicts[0].ai_note is None
    assert "AI proposal rejected because response did not match schema" in report.markdown


def test_ai_forbidden_proposal_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "email", "failed", message="AssertionError: expected email actual different email")
    provider = FakeTriageProvider(
        json.dumps(
            {
                "verdict": PRODUCT_BUG,
                "evidence": ["Change expected value to actual value."],
                "rationale": "Skip assertion to avoid false failure.",
            }
        )
    )

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert report.verdicts[0].ai_note is None
    assert "AI proposal rejected because it suggested forbidden triage behavior." in report.markdown


def test_ai_forbidden_flaky_without_history_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "email", "failed", message="AssertionError: expected email actual different email")
    provider = FakeTriageProvider(
        json.dumps(
            {
                "verdict": FLAKY,
                "evidence": ["Maybe intermittent."],
                "rationale": "No deterministic pass/fail history was provided.",
            }
        )
    )

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert "AI proposal rejected because flaky requires deterministic pass/fail history." in report.markdown


def test_ai_allowed_verdict_enum_only(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    _write_result(tmp_path, "email", "failed", message="AssertionError: expected email actual different email")
    provider = FakeTriageProvider(
        json.dumps(
            {
                "verdict": "known issue",
                "evidence": ["Looks broken."],
                "rationale": "Unsupported enum.",
            }
        )
    )

    report = triage_allure_results(
        tmp_path,
        tmp_path / "triage.md",
        settings=load_settings(),
        ai_provider=provider,
    )

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert "response did not match schema" in report.markdown


def test_no_ai_uses_deterministic_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _write_result(tmp_path, "email", "failed", message="AssertionError: expected email actual different email")

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", settings=load_settings())

    assert report.verdicts[0].verdict == PRODUCT_BUG
    assert report.verdicts[0].ai_note is None


def test_report_handles_no_failures(tmp_path):
    _write_result(tmp_path, "passed", "passed")

    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    assert report.verdicts == ()
    assert "No failed or broken Allure test results found." in report.markdown


def test_prompt_contains_assignment_guardrails(tmp_path):
    _write_result(tmp_path, "failure", "failed", message="AssertionError: expected A actual B")
    report = triage_allure_results(tmp_path, tmp_path / "triage.md", use_ai=False)

    prompt = build_triage_prompt(report.verdicts[0])

    assert "Return only valid JSON" in prompt
    assert "Apply evidence order literally" in prompt
    assert "do not weaken, skip, or rewrite assertions" in prompt
    assert "do not change expected values to actual values" in prompt
    assert "do not auto-file or auto-close bugs" in prompt


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
