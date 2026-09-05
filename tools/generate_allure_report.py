from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from edot_qa.config import ROOT_DIR, load_settings
from edot_qa.mobile.config import load_mobile_settings
from edot_qa.reporting.allure_metadata import EXPLICIT_TEST_CASE_IDS, apply_metadata_to_result, split_node_identifier
from edot_qa.reporting.allure_helpers import redact_payload


DEFAULT_CATEGORIES = ROOT_DIR / "edot_qa" / "reporting" / "allure_categories.json"
DEFAULT_TRIAGE_REPORT = ROOT_DIR / "reports" / "triage" / "triage-report.md"
TRIAGE_HISTORY_ID = "edot-evidence-ai-failure-triage-report"
TRIAGE_FULL_NAME = "tools.triage_allure_failures#triage_report"
TRIAGE_RESULT_NAME = "AI failure triage report"
FINAL_FAILURE_ATTACHMENT_NAMES = {
    "failure-evidence-call-page",
    "failure-evidence-call-screenshot",
    "failure-evidence-call page state",
    "failure-evidence-call screenshot",
    "Final failure page state",
    "Final failure screenshot",
}
STEP_FAILURE_ATTACHMENT_NAMES = {
    "step-failure-evidence-page",
    "step-failure-evidence-screenshot",
    "Failure page state",
    "Failure screenshot",
}
MOBILE_DEBUG_ATTACHMENT_NAMES = {
    "ai-test-data-used",
    "customer-card-locators-before-scroll",
    "customer-card-before-scroll",
    "customer-list-scroll-search",
    "maestro-command",
    "maestro-flow-yaml",
    "maestro-result",
    "maestro-stderr",
    "maestro-stdout",
    "mobile-customer-address-mapping",
    "mobile-customer-data",
    "mobile-device",
    "mobile-login-reset",
    "mobile-runtime-settings",
    "mobile-session-state",
    "mobile-start-app",
}
MOBILE_SCREENSHOT_RENAMES = {
    "customer-card-after-scroll-search": "Screenshot",
    "customer-card-visible-before-scroll": "Screenshot",
    "maestro-device-screenshot": "Screenshot",
}
MOBILE_CUSTOMER_RETURN_PAGE_STEP = "Return to new customer list. Expected: Customer list is displayed"
MOBILE_CUSTOMER_CARD_VALIDATION_STEP = (
    "Return to new customer list. Expected: created customer card matches submitted data"
)
STEP_NAME_RENAMES = {
    "Find created customer card from list bottom": MOBILE_CUSTOMER_CARD_VALIDATION_STEP,
    "Verify created customer card. Expected: name, address, and customer type match submitted data": (
        MOBILE_CUSTOMER_CARD_VALIDATION_STEP
    ),
    "Run Maestro flow: create_customer.yaml": "Create eWork customer",
    "Run Maestro flow: login.yaml": "Login to eWork",
    "Run Maestro flow: create_customer_basic.yaml": "Complete Basic customer page",
    "Run Maestro flow: create_customer_locations.yaml": "Complete Location page",
    "Run Maestro flow: create_customer_documents.yaml": "Complete Documents page",
}
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate eDOT Allure report with enriched metadata.")
    parser.add_argument("--results-dir", type=Path, default=ROOT_DIR / "reports" / "allure-results")
    parser.add_argument("--report-dir", type=Path, default=ROOT_DIR / "reports" / "allure-report")
    parser.add_argument("--categories", type=Path, default=DEFAULT_CATEGORIES)
    parser.add_argument("--triage-report", type=Path, default=DEFAULT_TRIAGE_REPORT)
    parser.add_argument("--no-triage", action="store_true", help="Do not attach reports/triage markdown to Allure.")
    parser.add_argument("--open", action="store_true", help="Open the generated report with the local Allure CLI.")
    args = parser.parse_args()

    results_dir = _resolve(args.results_dir)
    report_dir = _resolve(args.report_dir)
    categories_path = _resolve(args.categories)
    triage_report_path = _resolve(args.triage_report)

    results_dir.mkdir(parents=True, exist_ok=True)
    _copy_history(report_dir, results_dir)
    _write_environment(results_dir)
    _write_executor(results_dir)
    _copy_categories(categories_path, results_dir)
    removed_triage = _remove_existing_triage_results(results_dir)
    if removed_triage:
        print(f"[Allure Generate] Removed {removed_triage} older triage result file(s).")
    removed = _deduplicate_latest_results(results_dir)
    if removed:
        print(f"[Allure Generate] Removed {removed} older duplicate result file(s).")
    removed_non_reportable = _remove_non_reportable_results(results_dir)
    if removed_non_reportable:
        print(f"[Allure Generate] Removed {removed_non_reportable} support-only result file(s).")
    processed = _postprocess_results(results_dir)
    print(f"[Allure Generate] Enriched {processed} result file(s).")
    if not args.no_triage and _upsert_triage_result(results_dir, triage_report_path):
        print("[Allure Generate] Attached triage report to the shared Allure report.")

    command = _allure_command(ROOT_DIR)
    completed = subprocess.run(
        [*command, "generate", str(results_dir), "--clean", "-o", str(report_dir)],
        cwd=ROOT_DIR,
        check=False,
        shell=os.name == "nt" and command[0].lower().endswith(".cmd"),
    )
    if completed.returncode != 0:
        return completed.returncode

    _build_navigation_fallback(report_dir)
    print(f"[Allure Generate] Report ready: {report_dir}")
    if args.open:
        return subprocess.run([*command, "open", str(report_dir)], cwd=ROOT_DIR, check=False).returncode
    return 0


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT_DIR / path


def _copy_history(report_dir: Path, results_dir: Path) -> None:
    old_history = report_dir / "history"
    new_history = results_dir / "history"
    if old_history.is_dir():
        shutil.copytree(old_history, new_history, dirs_exist_ok=True)
        print("[Allure Generate] Copied previous report history.")


def _write_environment(results_dir: Path) -> None:
    settings = _safe_call(load_settings)
    mobile_settings = _safe_call(load_mobile_settings)

    values: dict[str, Any] = {
        "Project": "eDOT QA Automation Take-Home V4",
        "Execution_Environment": "Local Development",
        "Operating_System": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "Python_Version": platform.python_version(),
        "Execution_Time": datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
    if settings is not None:
        values.update(
            {
                "Base_URL": settings.esuite_base_url,
                "Browser": settings.browser,
                "Headless": settings.headless,
                "Storage_State": settings.storage_state_path,
                "AI_Test_Data_Model": settings.gemini_test_data_model,
                "AI_Triage_Model": settings.gemini_triage_model,
            }
        )
    if mobile_settings is not None:
        values.update(
            {
                "Mobile_App_ID": mobile_settings.ework_app_id or "<missing>",
                "Mobile_Device_ID": mobile_settings.mobile_device_id or "<auto>",
                "Maestro_CLI": mobile_settings.maestro_cli,
                "ADB_Command": mobile_settings.adb_command,
                "Maestro_Flow_Dir": mobile_settings.maestro_flow_dir,
            }
        )

    content = "\n".join(f"{key}={_property_value(value)}" for key, value in values.items()) + "\n"
    (results_dir / "environment.properties").write_text(content, encoding="utf-8")
    print("[Allure Generate] Wrote environment.properties.")


def _write_executor(results_dir: Path) -> None:
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    payload = {
        "name": socket.gethostname() or "Local Machine",
        "type": "local",
        "buildName": f"Run - {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "reportName": "eDOT QA Automation Test Report",
    }
    (results_dir / "executor.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("[Allure Generate] Wrote executor.json.")


def _copy_categories(categories_path: Path, results_dir: Path) -> None:
    if categories_path.is_file():
        shutil.copy2(categories_path, results_dir / "categories.json")
        print("[Allure Generate] Copied categories.json.")


def _deduplicate_latest_results(results_dir: Path) -> int:
    latest_by_test: dict[str, tuple[Path, int]] = {}
    old_results: list[Path] = []

    for result_path in sorted(results_dir.glob("*-result.json")):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"[Allure Generate] Skipped duplicate check for {result_path.name}: {error}")
            continue

        identity = _result_identity(payload)
        if not identity:
            continue

        timestamp = _result_timestamp(payload, result_path)
        current = latest_by_test.get(identity)
        if current is None:
            latest_by_test[identity] = (result_path, timestamp)
            continue

        current_path, current_timestamp = current
        if timestamp >= current_timestamp:
            old_results.append(current_path)
            latest_by_test[identity] = (result_path, timestamp)
        else:
            old_results.append(result_path)

    removed = 0
    for result_path in old_results:
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            _unlink_result_attachments(payload, results_dir)
        except (OSError, json.JSONDecodeError):
            pass
        try:
            result_path.unlink()
            removed += 1
        except OSError as error:
            print(f"[Allure Generate] Could not remove older result {result_path.name}: {error}")
    return removed


def _remove_non_reportable_results(results_dir: Path) -> int:
    removed = 0
    for result_path in sorted(results_dir.glob("*-result.json")):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"[Allure Generate] Skipped report-scope check for {result_path.name}: {error}")
            continue

        if _is_reportable_result(payload):
            continue

        _unlink_result_attachments(payload, results_dir)
        try:
            result_path.unlink()
            removed += 1
        except OSError as error:
            print(f"[Allure Generate] Could not remove support-only result {result_path.name}: {error}")
    return removed


def _is_reportable_result(payload: dict[str, Any]) -> bool:
    if payload.get("historyId") == TRIAGE_HISTORY_ID or payload.get("fullName") == TRIAGE_FULL_NAME:
        return True

    full_name = str(payload.get("fullName") or "")
    if full_name and _result_node_key(full_name) in EXPLICIT_TEST_CASE_IDS:
        return True

    tags = _result_tags(payload)
    if "deliberate_failure" in tags or "evidence" in tags or "ai" in tags:
        return True

    return False


def _result_node_key(identifier: str) -> str:
    path, test_name = split_node_identifier(identifier)
    clean_path = path.replace("\\", "/")
    return f"{clean_path}::{test_name}"


def _result_tags(payload: dict[str, Any]) -> set[str]:
    return {
        str(label.get("value"))
        for label in payload.get("labels", [])
        if label.get("name") == "tag" and label.get("value")
    }


def _result_identity(payload: dict[str, Any]) -> str | None:
    full_name = payload.get("fullName")
    if isinstance(full_name, str) and full_name.strip():
        return f"fullName:{full_name.strip()}|parameters:{_parameters_identity(payload)}"

    for key in ("historyId", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
    return None


def _parameters_identity(payload: dict[str, Any]) -> str:
    parameters = []
    for parameter in payload.get("parameters", []):
        name = parameter.get("name")
        if name == "test_case_id":
            continue
        parameters.append({"name": name, "value": parameter.get("value")})
    if not parameters:
        return ""
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def _result_timestamp(payload: dict[str, Any], result_path: Path) -> int:
    for key in ("stop", "start"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
    try:
        return result_path.stat().st_mtime_ns // 1_000_000
    except OSError:
        return 0


def _postprocess_results(results_dir: Path) -> int:
    count = 0
    for result_path in sorted(results_dir.glob("*-result.json")):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            _promote_nested_failure_status(payload)
            payload = apply_metadata_to_result(payload)
            _ensure_step_evidence(payload, results_dir)
            result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            count += 1
        except (OSError, json.JSONDecodeError) as error:
            print(f"[Allure Generate] Skipped {result_path.name}: {error}")
    return count


def _promote_nested_failure_status(result: dict[str, Any]) -> None:
    child_status = _first_child_failure_status(result.get("steps", []))
    if _status(result.get("status")) == "passed" and child_status in {"failed", "broken"}:
        result["status"] = child_status
        result.setdefault(
            "statusDetails",
            {"message": f"Nested step reported {child_status}; keeping report status consistent."},
        )


def _first_child_failure_status(steps: list[dict[str, Any]]) -> str | None:
    for step in steps:
        if not isinstance(step, dict):
            continue
        status = _status(step.get("status"))
        if status in {"failed", "broken"}:
            return status
        nested_status = _first_child_failure_status(step.get("steps", []))
        if nested_status is not None:
            return nested_status
    return None


def _upsert_triage_result(results_dir: Path, triage_report_path: Path) -> bool:
    if not triage_report_path.is_file():
        return False

    _remove_existing_triage_results(results_dir)
    triage_markdown = triage_report_path.read_text(encoding="utf-8")
    attachment_source = f"{uuid.uuid4()}-attachment.txt"
    (results_dir / attachment_source).write_text(triage_markdown, encoding="utf-8")
    now = int(datetime.now(ZoneInfo("Asia/Jakarta")).timestamp() * 1000)
    payload = {
        "uuid": str(uuid.uuid4()),
        "historyId": TRIAGE_HISTORY_ID,
        "testCaseId": TRIAGE_HISTORY_ID,
        "fullName": TRIAGE_FULL_NAME,
        "name": TRIAGE_RESULT_NAME,
        "description": triage_markdown,
        "status": "passed",
        "stage": "finished",
        "start": now,
        "stop": now,
        "labels": [
            {"name": "parentSuite", "value": "eDOT Evidence"},
            {"name": "suite", "value": "Evidence"},
            {"name": "subSuite", "value": "Failure Triage"},
            {"name": "epic", "value": "Evidence"},
            {"name": "feature", "value": "AI Failure Triage"},
            {"name": "story", "value": "Triage Markdown"},
            {"name": "severity", "value": "normal"},
            {"name": "owner", "value": "qa-automation"},
            {"name": "tag", "value": "triage"},
            {"name": "tag", "value": "evidence"},
        ],
        "steps": [
            {
                "name": "Attach AI failure triage markdown",
                "status": "passed",
                "stage": "finished",
                "start": now,
                "stop": now,
                "attachments": [
                    {
                        "name": "AI failure triage report",
                        "source": attachment_source,
                        "type": "text/plain",
                    }
                ],
                "steps": [],
            }
        ],
    }
    result_path = results_dir / f"{payload['uuid']}-result.json"
    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


def _remove_existing_triage_results(results_dir: Path) -> int:
    removed = 0
    for result_path in sorted(results_dir.glob("*-result.json")):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("historyId") != TRIAGE_HISTORY_ID and payload.get("fullName") != TRIAGE_FULL_NAME:
            continue
        _unlink_result_attachments(payload, results_dir)
        try:
            result_path.unlink()
            removed += 1
        except OSError as error:
            print(f"[Allure Generate] Could not remove old triage result {result_path.name}: {error}")
    return removed


def _unlink_result_attachments(payload: dict[str, Any], results_dir: Path) -> None:
    for source in _attachment_sources(payload):
        if not source:
            continue
        try:
            (results_dir / source).unlink(missing_ok=True)
        except OSError:
            continue


def _attachment_sources(node: dict[str, Any]) -> list[str]:
    sources = [str(attachment.get("source")) for attachment in node.get("attachments", []) if attachment.get("source")]
    for step in node.get("steps", []):
        if isinstance(step, dict):
            sources.extend(_attachment_sources(step))
    return sources


def _ensure_step_evidence(result: dict[str, Any], results_dir: Path) -> None:
    steps = result.setdefault("steps", [])
    mobile_result = _is_mobile_result(result)
    result["attachments"] = _clean_attachments(
        result.get("attachments", []),
        results_dir,
        drop_final_failure=_has_step_failure_evidence(steps),
        drop_mobile_debug=mobile_result,
    )
    result["steps"] = _compact_steps(steps, depth=0, results_dir=results_dir, drop_mobile_debug=mobile_result)
    steps = result["steps"]
    if not steps:
        summary = {
            "name": "Test summary",
            "status": _status(result.get("status")),
            "stage": "finished",
            "start": result.get("start"),
            "stop": result.get("stop"),
            "attachments": [],
        }
        _attach_summary(result, summary, results_dir)
        steps.append(summary)


def _attach_summary(result: dict[str, Any], step: dict[str, Any], results_dir: Path) -> None:
    source = f"{uuid.uuid4()}-attachment.json"
    labels = _labels_by_name(result.get("labels", []))
    payload = {
        "test": {
            "name": result.get("name"),
            "fullName": result.get("fullName"),
            "status": _status(result.get("status")),
        },
        "suite": {
            "parentSuite": labels.get("parentSuite"),
            "suite": labels.get("suite"),
            "subSuite": labels.get("subSuite"),
        },
        "behavior": {
            "epic": labels.get("epic"),
            "feature": labels.get("feature"),
            "story": labels.get("story"),
            "severity": labels.get("severity"),
            "owner": labels.get("owner"),
        },
        "tags": labels.get("tag", []),
        "parameters": result.get("parameters", []),
    }
    (results_dir / source).write_text(json.dumps(redact_payload(payload), indent=2, sort_keys=True), encoding="utf-8")
    step.setdefault("attachments", []).append(
        {
            "name": "Summary",
            "source": source,
            "type": "application/json",
        }
    )


def _compact_steps(
    steps: list[dict[str, Any]],
    *,
    depth: int,
    results_dir: Path,
    drop_mobile_debug: bool,
) -> list[dict[str, Any]]:
    compacted = []
    for step in steps:
        if step.get("name") in STEP_NAME_RENAMES:
            step["name"] = STEP_NAME_RENAMES[str(step["name"])]
        step["attachments"] = _clean_attachments(
            step.get("attachments", []),
            results_dir,
            drop_mobile_debug=drop_mobile_debug,
        )
        step["steps"] = _compact_steps(
            step.get("steps", []),
            depth=depth + 1,
            results_dir=results_dir,
            drop_mobile_debug=drop_mobile_debug,
        )
        if drop_mobile_debug:
            _move_mobile_customer_card_evidence_into_return_step(step)
        if (depth > 0 or drop_mobile_debug) and _is_empty_passed_step(step):
            continue
        compacted.append(step)
    if drop_mobile_debug:
        compacted = _drop_redundant_mobile_customer_return_step(compacted)
    return compacted


def _drop_redundant_mobile_customer_return_step(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    has_card_validation = any(step.get("name") == MOBILE_CUSTOMER_CARD_VALIDATION_STEP for step in steps)
    if not has_card_validation:
        return steps
    return [step for step in steps if step.get("name") != MOBILE_CUSTOMER_RETURN_PAGE_STEP]


def _move_mobile_customer_card_evidence_into_return_step(step: dict[str, Any]) -> None:
    attachments = step.get("attachments", [])
    expected_card = next((attachment for attachment in attachments if attachment.get("name") == "Expected card"), None)
    card_screenshot = next((attachment for attachment in attachments if attachment.get("name") == "Screenshot"), None)
    if expected_card is None or card_screenshot is None:
        return

    return_step = next(
        (
            child
            for child in step.get("steps", [])
            if child.get("name") in {MOBILE_CUSTOMER_RETURN_PAGE_STEP, MOBILE_CUSTOMER_CARD_VALIDATION_STEP}
        ),
        None,
    )
    if return_step is None:
        return

    return_step["name"] = MOBILE_CUSTOMER_CARD_VALIDATION_STEP
    return_step["attachments"] = [expected_card, card_screenshot]
    step["attachments"] = [
        attachment
        for attachment in attachments
        if attachment is not expected_card and attachment is not card_screenshot
    ]


def _clean_attachments(
    attachments: list[dict[str, Any]],
    results_dir: Path,
    *,
    drop_final_failure: bool = False,
    drop_mobile_debug: bool = False,
) -> list[dict[str, Any]]:
    cleaned = []
    input_records = []
    for attachment in attachments:
        name = str(attachment.get("name", ""))
        if drop_final_failure and name in FINAL_FAILURE_ATTACHMENT_NAMES:
            continue
        if drop_mobile_debug and name in MOBILE_DEBUG_ATTACHMENT_NAMES:
            continue
        if name in {
            "step-runtime-info",
            "step-result",
            "step-evidence-page",
            "step-evidence-screenshot",
        }:
            continue
        if name in {"step-input", "Input"} or name.startswith("Input - "):
            input_records.append(
                {
                    "step": name.removeprefix("Input - ") if name.startswith("Input - ") else "Input",
                    "data": _read_json_attachment(results_dir, attachment),
                }
            )
            continue
        renamed = dict(attachment)
        renamed["name"] = {
            "step-error": "Error",
            "step-failure-evidence-page": "Failure page state",
            "step-failure-evidence-screenshot": "Failure screenshot",
            "failure-evidence-call-page": "Final failure page state",
            "failure-evidence-call-screenshot": "Final failure screenshot",
            "failure-evidence-call page state": "Final failure page state",
            "failure-evidence-call screenshot": "Final failure screenshot",
            **MOBILE_SCREENSHOT_RENAMES,
        }.get(name, name)
        cleaned.append(renamed)
    if input_records:
        source = f"{uuid.uuid4()}-attachment.json"
        (results_dir / source).write_text(
            json.dumps(_combine_input_records(input_records), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        cleaned.insert(0, {"name": "Inputs", "source": source, "type": "application/json"})
    return cleaned


def _has_step_failure_evidence(steps: list[dict[str, Any]]) -> bool:
    for step in steps:
        if not isinstance(step, dict):
            continue
        attachment_names = {str(attachment.get("name", "")) for attachment in step.get("attachments", [])}
        if attachment_names & STEP_FAILURE_ATTACHMENT_NAMES:
            return True
        if _has_step_failure_evidence(step.get("steps", [])):
            return True
    return False


def _read_json_attachment(results_dir: Path, attachment: dict[str, Any]) -> Any:
    source = attachment.get("source")
    if not source:
        return {}
    try:
        return json.loads((results_dir / str(source)).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"source": source}


def _combine_input_records(records: list[dict[str, Any]]) -> Any:
    fields: dict[str, Any] = {}
    items = []
    for record in records:
        data = record.get("data")
        if isinstance(data, dict) and {"field", "value"}.issubset(data):
            fields[str(data["field"])] = data["value"]
            continue
        items.append(record)
    if fields:
        return {"fields": redact_payload(fields)}
    if len(items) == 1:
        return redact_payload(items[0].get("data"))
    return redact_payload({"items": items})


def _is_empty_passed_step(step: dict[str, Any]) -> bool:
    return _status(step.get("status")) == "passed" and not step.get("attachments") and not step.get("steps")


def _is_mobile_result(result: dict[str, Any]) -> bool:
    full_name = str(result.get("fullName") or "")
    if "tests.mobile." in full_name or "tests/mobile/" in full_name:
        return True
    return any(label.get("name") == "tag" and label.get("value") == "mobile" for label in result.get("labels", []))


def _labels_by_name(labels: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, Any] = {}
    for label in labels:
        name = label.get("name")
        value = label.get("value")
        if not name or value is None:
            continue
        if name == "tag":
            grouped.setdefault(name, []).append(value)
        else:
            grouped.setdefault(name, value)
    return grouped


def _allure_command(root: Path) -> list[str]:
    local_dist = root / "node_modules" / "allure-commandline" / "dist"
    java_executable = _java_executable()
    if local_dist.is_dir() and java_executable:
        classpath = os.pathsep.join([str(local_dist / "lib" / "*"), str(local_dist / "lib" / "config")])
        return [java_executable, "-classpath", classpath, "io.qameta.allure.CommandLine"]
    local_bin = root / "node_modules" / ".bin" / ("allure.cmd" if os.name == "nt" else "allure")
    if local_bin.exists():
        return [str(local_bin)]
    global_bin = shutil.which("allure")
    if global_bin:
        return [global_bin]
    raise SystemExit("Allure CLI not found. Run `npm install` first or install Allure globally.")


def _java_executable() -> str | None:
    java_home = os.getenv("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.exists():
            return str(candidate)
    return shutil.which("java")


def _build_navigation_fallback(report_dir: Path) -> None:
    cases_dir = report_dir / "data" / "test-cases"
    if not cases_dir.is_dir():
        return

    cases = []
    for case_path in cases_dir.glob("*.json"):
        try:
            case = json.loads(case_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if case.get("uid") and case.get("name"):
            cases.append(case)
    if not cases:
        return

    behaviors = _build_tree(
        "behaviors",
        cases,
        lambda case: [
            _label(case, "epic", "eDOT QA Automation"),
            _label(case, "feature", "General"),
            _label(case, "story", "General"),
        ],
    )
    packages = _build_tree(
        "packages",
        cases,
        lambda case: _label(case, "package", "unknown.package").split("."),
    )

    data_dir = report_dir / "data"
    widgets_dir = report_dir / "widgets"
    data_dir.mkdir(parents=True, exist_ok=True)
    widgets_dir.mkdir(parents=True, exist_ok=True)

    _write_json(data_dir / "behaviors.json", behaviors)
    _write_json(data_dir / "packages.json", packages)
    _write_json(widgets_dir / "behaviors.json", _widget_summary(behaviors))
    _write_json(widgets_dir / "packages.json", _widget_summary(packages))
    _write_csv(data_dir / "behaviors.csv", behaviors)
    _write_csv(data_dir / "packages.csv", packages)
    print("[Allure Generate] Ensured behavior/package navigation data.")


def _build_tree(name: str, cases: list[dict[str, Any]], group_factory: Callable[[dict[str, Any]], list[str]]) -> dict[str, Any]:
    root: dict[str, Any] = {"uid": _uid(name), "name": name, "children": []}
    for case in cases:
        current = root
        parts: list[str] = []
        for raw_part in [part for part in group_factory(case) if part]:
            part = raw_part or "General"
            parts.append(part)
            children = current.setdefault("children", [])
            child = next((item for item in children if item.get("name") == part and "children" in item), None)
            if child is None:
                child = {"name": part, "children": [], "uid": _uid(" > ".join(parts))}
                children.append(child)
            current = child
        current.setdefault("children", []).append(_leaf(case, current["uid"]))
    root["statistic"] = _compute_stats(root)
    _sort_tree(root)
    return root


def _leaf(case: dict[str, Any], parent_uid: str) -> dict[str, Any]:
    return {
        "name": case.get("name"),
        "uid": case.get("uid"),
        "parentUid": parent_uid,
        "status": _status(case.get("status")),
        "time": case.get("time"),
        "flaky": bool(case.get("flaky")),
        "newFailed": bool(case.get("newFailed")),
        "newPassed": bool(case.get("newPassed")),
        "newBroken": bool(case.get("newBroken")),
        "retriesCount": case.get("retriesCount") or 0,
        "retriesStatusChange": bool(case.get("retriesStatusChange")),
        "parameters": case.get("parameterValues") or [parameter.get("value") for parameter in case.get("parameters", [])],
        "tags": [label.get("value") for label in case.get("labels", []) if label.get("name") == "tag"],
    }


def _compute_stats(node: dict[str, Any]) -> dict[str, int]:
    stats = {status: 0 for status in ("failed", "broken", "skipped", "passed", "unknown")}
    stats["total"] = 0
    for child in node.get("children", []):
        if "children" in child:
            child["statistic"] = _compute_stats(child)
            for key, value in child["statistic"].items():
                stats[key] += value
        else:
            stats[_status(child.get("status"))] += 1
            stats["total"] += 1
    return stats


def _sort_tree(node: dict[str, Any]) -> None:
    node.get("children", []).sort(key=lambda item: (0 if "children" in item else 1, str(item.get("name", ""))))
    for child in node.get("children", []):
        if "children" in child:
            _sort_tree(child)


def _widget_summary(tree: dict[str, Any]) -> dict[str, Any]:
    children = tree.get("children", [])
    return {
        "total": len(children),
        "items": [
            {"uid": child.get("uid"), "name": child.get("name"), "statistic": child.get("statistic", {})}
            for child in children
        ],
    }


def _write_csv(path: Path, tree: dict[str, Any]) -> None:
    rows = [["Path", "Status", "Name"]]

    def visit(node: dict[str, Any], ancestors: list[str]) -> None:
        for child in node.get("children", []):
            if "children" in child:
                visit(child, [*ancestors, str(child.get("name"))])
            else:
                rows.append([" > ".join(ancestors), str(child.get("status")), str(child.get("name"))])

    visit(tree, [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def _label(case: dict[str, Any], name: str, fallback: str) -> str:
    for label in case.get("labels", []):
        if label.get("name") == name and label.get("value"):
            return str(label["value"])
    return fallback


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _status(value: Any) -> str:
    text = str(value or "unknown")
    return text if text in {"failed", "broken", "skipped", "passed", "unknown"} else "unknown"


def _uid(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _property_value(value: Any) -> str:
    return str(value).replace("\\", "/").replace("\n", " ").replace("\r", " ")


def _safe_call(function: Callable[[], Any]) -> Any | None:
    try:
        return function()
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
