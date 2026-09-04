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
from edot_qa.reporting.allure_metadata import apply_metadata_to_result
from edot_qa.reporting.allure_helpers import redact_payload


DEFAULT_CATEGORIES = ROOT_DIR / "edot_qa" / "reporting" / "allure_categories.json"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate eDOT Allure report with enriched metadata.")
    parser.add_argument("--results-dir", type=Path, default=ROOT_DIR / "reports" / "allure-results")
    parser.add_argument("--report-dir", type=Path, default=ROOT_DIR / "reports" / "allure-report")
    parser.add_argument("--categories", type=Path, default=DEFAULT_CATEGORIES)
    parser.add_argument("--open", action="store_true", help="Open the generated report with the local Allure CLI.")
    args = parser.parse_args()

    results_dir = _resolve(args.results_dir)
    report_dir = _resolve(args.report_dir)
    categories_path = _resolve(args.categories)

    results_dir.mkdir(parents=True, exist_ok=True)
    _copy_history(report_dir, results_dir)
    _write_environment(results_dir)
    _write_executor(results_dir)
    _copy_categories(categories_path, results_dir)
    processed = _postprocess_results(results_dir)
    print(f"[Allure Generate] Enriched {processed} result file(s).")

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


def _postprocess_results(results_dir: Path) -> int:
    count = 0
    for result_path in sorted(results_dir.glob("*-result.json")):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            payload = apply_metadata_to_result(payload)
            _ensure_step_evidence(payload, results_dir)
            result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            count += 1
        except (OSError, json.JSONDecodeError) as error:
            print(f"[Allure Generate] Skipped {result_path.name}: {error}")
    return count


def _ensure_step_evidence(result: dict[str, Any], results_dir: Path) -> None:
    steps = result.setdefault("steps", [])
    if not steps:
        steps.append(
            {
                "name": "Test evidence summary",
                "status": _status(result.get("status")),
                "stage": "finished",
                "start": result.get("start"),
                "stop": result.get("stop"),
                "attachments": [],
            }
        )

    for step in _iter_steps(steps):
        _attach_step_runtime_info(result, step, results_dir)


def _iter_steps(steps: list[dict[str, Any]]):
    for step in steps:
        yield step
        yield from _iter_steps(step.get("steps", []))


def _attach_step_runtime_info(result: dict[str, Any], step: dict[str, Any], results_dir: Path) -> None:
    if any(attachment.get("name") == "step-runtime-info" for attachment in step.get("attachments", [])):
        return

    source = f"{uuid.uuid4()}-attachment.json"
    labels = _labels_by_name(result.get("labels", []))
    payload = {
        "test": {
            "name": result.get("name"),
            "fullName": result.get("fullName"),
            "status": _status(result.get("status")),
        },
        "step": {
            "name": step.get("name"),
            "status": _status(step.get("status")),
            "stage": step.get("stage"),
            "start": step.get("start"),
            "stop": step.get("stop"),
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
            "name": "step-runtime-info",
            "source": source,
            "type": "application/json",
        }
    )


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
