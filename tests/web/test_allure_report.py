from __future__ import annotations

import json
from pathlib import Path

from tools.generate_allure_report import TRIAGE_HISTORY_ID, _postprocess_results, _upsert_triage_result


def test_allure_generator_attaches_triage_as_inline_text(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    triage_report = tmp_path / "triage-report.md"
    triage_report.write_text("# Triage\n\nHuman-review proposal.", encoding="utf-8")

    assert _upsert_triage_result(results_dir, triage_report) is True

    payload = json.loads(next(results_dir.glob("*-result.json")).read_text(encoding="utf-8"))
    attachment = payload["steps"][0]["attachments"][0]
    assert payload["historyId"] == TRIAGE_HISTORY_ID
    assert payload["description"] == "# Triage\n\nHuman-review proposal."
    assert attachment["type"] == "text/plain"
    assert (results_dir / attachment["source"]).read_text(encoding="utf-8") == "# Triage\n\nHuman-review proposal."


def test_allure_generator_keeps_deliberate_failure_red(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    result_path = results_dir / "deliberate-result.json"
    result_path.write_text(
        json.dumps(
            {
                "name": "test_web_login_wrong_button_locator_records_real_failure",
                "fullName": "tests.web.test_login#test_web_login_wrong_button_locator_records_real_failure",
                "status": "failed",
                "statusDetails": {"message": "AssertionError: wrong locator"},
                "labels": [{"name": "tag", "value": "deliberate_failure"}],
            }
        ),
        encoding="utf-8",
    )

    _postprocess_results(results_dir)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    labels = {label["name"]: label["value"] for label in payload["labels"] if label["name"] != "tag"}
    assert payload["status"] == "failed"
    assert labels["parentSuite"] == "eDOT Evidence"
    assert labels["subSuite"] == "Deliberate Failure"


def test_allure_generator_cleans_duplicate_tags_and_failure_attachment_names(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    result_path = results_dir / "failure-result.json"
    result_path.write_text(
        json.dumps(
            {
                "name": "test_web_login_wrong_button_locator_records_real_failure",
                "fullName": "tests.web.test_login#test_web_login_wrong_button_locator_records_real_failure",
                "status": "failed",
                "statusDetails": {"message": "AssertionError: wrong locator"},
                "attachments": [
                    {"name": "failure-evidence-call page state", "source": "page.json", "type": "application/json"},
                    {"name": "failure-evidence-call screenshot", "source": "screen.png", "type": "image/png"},
                ],
                "labels": [
                    {"name": "tag", "value": "web"},
                    {"name": "tag", "value": "web"},
                    {"name": "tag", "value": "deliberate_failure"},
                    {"name": "tag", "value": "deliberate_failure"},
                ],
            }
        ),
        encoding="utf-8",
    )

    _postprocess_results(results_dir)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    tags = [label["value"] for label in payload["labels"] if label["name"] == "tag"]
    attachments = [attachment["name"] for attachment in payload["attachments"]]
    assert tags.count("web") == 1
    assert tags.count("deliberate_failure") == 1
    assert attachments == ["Final failure page state", "Final failure screenshot"]
