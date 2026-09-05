from __future__ import annotations

import json
from pathlib import Path

from tools.generate_allure_report import (
    TRIAGE_HISTORY_ID,
    _deduplicate_latest_results,
    _postprocess_results,
    _remove_non_reportable_results,
    _upsert_triage_result,
)


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
    assert payload["name"] == "Web Wrong Login Button Locator"
    assert labels["parentSuite"] == "eDOT Evidence"
    assert labels["subSuite"] == "Deliberate Failure"


def test_allure_generator_uses_human_readable_test_names(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    result_path = results_dir / "company-result.json"
    result_path.write_text(
        json.dumps(
            {
                "name": "test_create_company_three_step_wizard_with_ai_data",
                "fullName": "tests.web.test_create_company#test_create_company_three_step_wizard_with_ai_data",
                "status": "passed",
            }
        ),
        encoding="utf-8",
    )

    _postprocess_results(results_dir)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["name"] == "Create Company Through Three Step Wizard"
    assert "_" not in payload["name"]


def test_allure_generator_cleans_duplicate_tags_and_drops_redundant_final_failure(tmp_path: Path) -> None:
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
                "steps": [
                    {
                        "name": "Failed page step",
                        "status": "failed",
                        "attachments": [
                            {"name": "Failure page state", "source": "step-page.json", "type": "application/json"},
                            {"name": "Failure screenshot", "source": "step-screen.png", "type": "image/png"},
                        ],
                    }
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
    step_attachments = [attachment["name"] for attachment in payload["steps"][0]["attachments"]]
    assert tags.count("web") == 1
    assert tags.count("deliberate_failure") == 1
    assert attachments == []
    assert step_attachments == ["Failure page state", "Failure screenshot"]


def test_allure_generator_keeps_mobile_report_lean(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    result_path = results_dir / "mobile-result.json"
    result_path.write_text(
        json.dumps(
            {
                "name": "test_ework_create_customer_appears_with_correct_data",
                "fullName": "tests.mobile.test_mobile_create_customer#test_ework_create_customer_appears_with_correct_data",
                "status": "passed",
                "steps": [
                    {
                        "name": "Run Maestro flow: create_customer_basic.yaml",
                        "status": "passed",
                        "attachments": [
                            {"name": "Inputs", "source": "inputs.json", "type": "application/json"},
                            {"name": "maestro-command", "source": "command.json", "type": "application/json"},
                            {"name": "maestro-flow-yaml", "source": "flow.yaml", "type": "text/plain"},
                            {"name": "maestro-stdout", "source": "stdout.txt", "type": "text/plain"},
                            {"name": "maestro-stderr", "source": "stderr.txt", "type": "text/plain"},
                            {"name": "maestro-result", "source": "result.json", "type": "application/json"},
                            {"name": "maestro-device-screenshot", "source": "screen.png", "type": "image/png"},
                        ],
                    },
                    {
                        "name": "Generate mobile customer data",
                        "status": "passed",
                        "attachments": [
                            {"name": "ai-test-data-used", "source": "ai.json", "type": "application/json"},
                            {"name": "mobile-customer-data", "source": "customer.json", "type": "application/json"},
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (results_dir / "inputs.json").write_text('{"fields":{"Outlet Name":"Budi QA"}}', encoding="utf-8")

    _postprocess_results(results_dir)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    flow_attachments = [attachment["name"] for attachment in payload["steps"][0]["attachments"]]
    assert flow_attachments == ["Inputs", "Screenshot"]
    assert [step["name"] for step in payload["steps"]] == ["Run Maestro flow: create_customer_basic.yaml"]


def test_allure_generator_removes_support_only_results_from_main_report(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    helper_result = results_dir / "helper-result.json"
    live_result = results_dir / "live-result.json"
    helper_attachment = results_dir / "helper-attachment.json"
    helper_attachment.write_text("{}", encoding="utf-8")
    helper_result.write_text(
        json.dumps(
            {
                "name": "test_customer_card_visibility_requires_name_address_and_type",
                "fullName": (
                    "tests.mobile.test_mobile_create_customer"
                    "#test_customer_card_visibility_requires_name_address_and_type"
                ),
                "status": "passed",
                "attachments": [{"name": "Summary", "source": helper_attachment.name, "type": "application/json"}],
            }
        ),
        encoding="utf-8",
    )
    live_result.write_text(
        json.dumps(
            {
                "name": "test_ework_create_customer_appears_with_correct_data",
                "fullName": "tests.mobile.test_mobile_create_customer#test_ework_create_customer_appears_with_correct_data",
                "status": "passed",
            }
        ),
        encoding="utf-8",
    )

    assert _remove_non_reportable_results(results_dir) == 1

    assert not helper_result.exists()
    assert not helper_attachment.exists()
    assert live_result.exists()


def test_allure_generator_promotes_broken_child_step_to_result_status(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    result_path = results_dir / "mobile-interrupted-result.json"
    result_path.write_text(
        json.dumps(
            {
                "name": "test_ework_create_customer_appears_with_correct_data",
                "fullName": "tests.mobile.test_mobile_create_customer#test_ework_create_customer_appears_with_correct_data",
                "status": "passed",
                "steps": [
                    {
                        "name": "Run Maestro flow: create_customer_basic.yaml",
                        "status": "broken",
                        "statusDetails": {"message": "KeyboardInterrupt"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    _postprocess_results(results_dir)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["status"] == "broken"
    assert "Nested step reported broken" in payload["statusDetails"]["message"]


def test_allure_generator_deduplicates_same_test_when_history_id_is_missing(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    older = results_dir / "older-result.json"
    newer = results_dir / "newer-result.json"
    old_attachment = results_dir / "old-attachment.json"
    old_attachment.write_text("{}", encoding="utf-8")
    full_name = "tests.mobile.test_mobile_create_customer#test_ework_create_customer_appears_with_correct_data"
    older.write_text(
        json.dumps(
            {
                "name": "test_ework_create_customer_appears_with_correct_data",
                "fullName": full_name,
                "historyId": "fad7049c7a4ed0cae22eb8601108f1fb",
                "status": "passed",
                "start": 100,
                "stop": 200,
                "attachments": [{"name": "Old screenshot", "source": old_attachment.name, "type": "image/png"}],
            }
        ),
        encoding="utf-8",
    )
    newer.write_text(
        json.dumps(
            {
                "name": "test_ework_create_customer_appears_with_correct_data",
                "fullName": full_name,
                "status": "passed",
                "start": 300,
                "stop": 400,
            }
        ),
        encoding="utf-8",
    )

    assert _deduplicate_latest_results(results_dir) == 1

    assert not older.exists()
    assert not old_attachment.exists()
    assert newer.exists()


def test_allure_generator_deduplicates_only_same_test_identity(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    web_login = results_dir / "web-login-result.json"
    mobile_login = results_dir / "mobile-login-result.json"
    web_login.write_text(
        json.dumps(
            {
                "name": "test_esuite_login_shows_dashboard_greeting",
                "fullName": "tests.web.test_login#test_esuite_login_shows_dashboard_greeting",
                "status": "passed",
                "start": 100,
                "stop": 200,
            }
        ),
        encoding="utf-8",
    )
    mobile_login.write_text(
        json.dumps(
            {
                "name": "test_ework_login_displays_dashboard",
                "fullName": "tests.mobile.test_mobile_login#test_ework_login_displays_dashboard",
                "status": "passed",
                "start": 300,
                "stop": 400,
            }
        ),
        encoding="utf-8",
    )

    assert _deduplicate_latest_results(results_dir) == 0

    assert web_login.exists()
    assert mobile_login.exists()


def test_allure_generator_keeps_different_parameterized_runs(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    first = results_dir / "first-result.json"
    second = results_dir / "second-result.json"
    full_name = "tests.ai.test_example#test_case"
    first.write_text(
        json.dumps(
            {
                "name": "test_case[web]",
                "fullName": full_name,
                "status": "passed",
                "start": 100,
                "stop": 200,
                "parameters": [{"name": "platform", "value": "web"}],
            }
        ),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(
            {
                "name": "test_case[mobile]",
                "fullName": full_name,
                "status": "passed",
                "start": 300,
                "stop": 400,
                "parameters": [{"name": "platform", "value": "mobile"}],
            }
        ),
        encoding="utf-8",
    )

    assert _deduplicate_latest_results(results_dir) == 0

    assert first.exists()
    assert second.exists()


def test_allure_generator_keeps_ai_results_in_main_report(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    ai_result = results_dir / "ai-result.json"
    ai_result.write_text(
        json.dumps(
            {
                "name": "test_faker_fallback_is_deterministic",
                "fullName": "tests.ai.test_test_data#test_faker_fallback_is_deterministic",
                "status": "passed",
                "labels": [{"name": "tag", "value": "ai"}],
            }
        ),
        encoding="utf-8",
    )

    assert _remove_non_reportable_results(results_dir) == 0

    assert ai_result.exists()
