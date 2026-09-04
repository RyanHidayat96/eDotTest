from __future__ import annotations

from pathlib import Path

from tools.evidence_workflow import (
    DELIBERATE_FAILURE_ENV,
    DELIBERATE_FAILURE_MODE,
    build_deliberate_failure_plan,
    build_full_web_plan,
    render_findings,
    scan_evidence_dir,
    validate_generated_path,
)


def test_full_web_plan_runs_required_web_scenarios_before_report() -> None:
    plan = build_full_web_plan()
    commands = [" ".join(command.command) for command in plan.commands]

    assert plan.commands[0].continue_after_failure is True
    assert "tests/web/test_login.py" in commands[0]
    assert "tests/web/test_create_company.py" in commands[0]
    assert "tools/generate_allure_report.py" in commands[1]
    assert "evidence/web-allure" in commands[1]


def test_deliberate_failure_plan_sets_isolated_expected_failure() -> None:
    plan = build_deliberate_failure_plan()
    deliberate_step = plan.commands[0]

    assert deliberate_step.expected_failure is True
    assert (DELIBERATE_FAILURE_ENV, DELIBERATE_FAILURE_MODE) in deliberate_step.env
    assert "test_deliberate_failure_evidence.py" in " ".join(deliberate_step.command)


def test_evidence_generated_paths_are_limited_to_reports_or_evidence() -> None:
    plans = [build_full_web_plan(), build_deliberate_failure_plan()]
    messages = []
    for plan in plans:
        for path in plan.clean_paths:
            validate_generated_path(path)
            messages.append(f"{plan.name}:{path.as_posix()}")

    assert any("evidence/web-allure" in message for message in messages)
    assert any("reports/allure-results-deliberate" in message for message in messages)


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
