from __future__ import annotations

import json
from pathlib import Path

from tools.generate_allure_report import TRIAGE_HISTORY_ID, _upsert_triage_result
from tools.evidence_workflow import (
    DELIBERATE_FAILURE_ENV,
    DELIBERATE_FAILURE_MODE,
    build_deliberate_failure_plan,
    render_findings,
    scan_evidence_dir,
    validate_generated_path,
)


def test_deliberate_failure_plan_sets_shared_expected_failure() -> None:
    plan = build_deliberate_failure_plan()
    deliberate_step = plan.commands[0]
    commands = [" ".join(command.command) for command in plan.commands]

    assert deliberate_step.expected_failure is True
    assert (DELIBERATE_FAILURE_ENV, DELIBERATE_FAILURE_MODE) in deliberate_step.env
    assert "test_deliberate_failure_evidence.py" in " ".join(deliberate_step.command)
    assert "--clean-alluredir" not in " ".join(deliberate_step.command)
    assert "reports/allure-results" in commands[0]
    assert "reports/triage/triage-report.md" in commands[1]
    assert "reports/allure-report" in commands[2]


def test_evidence_generated_paths_are_limited_to_reports_or_evidence() -> None:
    plans = [build_deliberate_failure_plan()]
    messages = []
    for plan in plans:
        for path in plan.clean_paths:
            validate_generated_path(path)
            messages.append(f"{plan.name}:{path.as_posix()}")

    assert any("reports/triage" in message for message in messages)


def test_generated_path_rejects_non_artifact_target(tmp_path: Path) -> None:
    try:
        validate_generated_path(Path("README.md"), root=tmp_path)
    except ValueError as error:
        assert "reports/ or evidence/" in str(error)
    else:
        raise AssertionError("README.md should not be a generated evidence target")


def test_evidence_scan_rejects_known_secret_without_printing_value(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    secret_value = "sample-secret-value"
    evidence_dir.joinpath("report.json").write_text(f'{{"note":"{secret_value}"}}', encoding="utf-8")

    findings = scan_evidence_dir(evidence_dir, root=tmp_path, secret_values=[secret_value])
    rendered = render_findings(findings)

    assert "known secret value detected" in rendered
    assert secret_value not in rendered


def test_evidence_scan_allows_missing_empty_evidence_dir(tmp_path: Path) -> None:
    findings = scan_evidence_dir(tmp_path / "evidence", root=tmp_path, secret_values=[])

    assert findings == []


def test_allure_generator_attaches_triage_as_inline_text(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    triage_report = tmp_path / "triage-report.md"
    triage_report.write_text("# Triage\n\nHuman-review proposal.", encoding="utf-8")

    assert _upsert_triage_result(results_dir, triage_report) is True

    payload = json.loads(next(results_dir.glob("*-result.json")).read_text(encoding="utf-8"))
    attachment = payload["steps"][0]["attachments"][0]
    assert payload["historyId"] == TRIAGE_HISTORY_ID
    assert attachment["type"] == "text/plain"
    assert (results_dir / attachment["source"]).read_text(encoding="utf-8") == "# Triage\n\nHuman-review proposal."
