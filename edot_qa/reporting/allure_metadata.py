from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


try:
    import allure
except ModuleNotFoundError:
    allure = None


CONTROLLED_LABELS = {
    "parentSuite",
    "suite",
    "subSuite",
    "epic",
    "feature",
    "story",
    "severity",
    "owner",
}
IGNORED_MARKERS = {"parametrize", "skipif", "usefixtures", "filterwarnings"}

EXPLICIT_TEST_CASE_IDS = {
    "tests/web/test_login.py::test_esuite_login_shows_dashboard_greeting": "WEB-LOGIN-001",
    "tests/web/test_create_company.py::test_register_company_step_one_requires_valid_data": "WEB-COMPANY-001",
    "tests/web/test_create_company.py::test_create_company_three_step_wizard_with_ai_data": "WEB-COMPANY-002",
    "tests/web/test_web_mobile_handoff.py::test_web_created_company_handoff_drives_mobile_login": "E2E-WEB-MOBILE-001",
    "tests/mobile/test_mobile_login.py::test_ework_login_displays_dashboard": "MOBILE-LOGIN-001",
    "tests/mobile/test_mobile_create_customer.py::test_ework_create_customer_appears_with_correct_data": "MOBILE-CUSTOMER-001",
}


@dataclass(frozen=True)
class AllureMetadata:
    parent_suite: str
    suite: str
    sub_suite: str
    epic: str
    feature: str
    story: str
    severity: str
    owner: str
    tags: tuple[str, ...]
    test_case_id: str | None = None


def metadata_for_node(node_id: str, marker_names: Iterable[str] = ()) -> AllureMetadata:
    path, test_name = split_node_identifier(node_id)
    file_name = Path(path).name
    markers = {marker for marker in marker_names if marker not in IGNORED_MARKERS}

    if file_name == "test_web_mobile_handoff.py" or "e2e" in markers:
        metadata = _metadata(
            parent_suite="eDOT Cross Platform",
            suite="E2E",
            sub_suite="Web to Mobile Handoff",
            epic="eDOT Cross Platform",
            feature="Company Handoff",
            story="Web Company Drives Mobile Login",
            severity="critical",
            tags={"e2e", "web", "mobile", "handoff"},
        )
    elif file_name == "test_web_quality_gates.py":
        metadata = _metadata(
            parent_suite="Project Quality",
            suite="Quality",
            sub_suite="Repository Guardrails",
            epic="Project Quality",
            feature="Quality Gates",
            story=_humanize_test_name(test_name),
            severity="normal",
            tags={"quality", "guardrails"},
        )
    elif "/web/" in path:
        metadata = _web_metadata(file_name, test_name)
    elif "/mobile/" in path:
        metadata = _mobile_metadata(file_name, test_name)
    elif "/ai/" in path:
        metadata = _ai_metadata(file_name, test_name)
    else:
        metadata = _metadata(
            parent_suite="eDOT QA Automation",
            suite="General",
            sub_suite=_humanize_file_name(file_name),
            epic="eDOT QA Automation",
            feature="General",
            story=_humanize_test_name(test_name),
            severity="normal",
            tags={"edot"},
        )

    clean_path = path.replace("\\", "/")
    case_id = EXPLICIT_TEST_CASE_IDS.get(f"{clean_path}::{test_name}")
    tags = tuple(sorted(set(metadata.tags) | markers | {"edot"} | ({case_id} if case_id else set())))
    return AllureMetadata(
        parent_suite=metadata.parent_suite,
        suite=metadata.suite,
        sub_suite=metadata.sub_suite,
        epic=metadata.epic,
        feature=metadata.feature,
        story=metadata.story,
        severity=metadata.severity,
        owner=metadata.owner,
        tags=tags,
        test_case_id=case_id,
    )


def apply_allure_metadata(item: Any) -> AllureMetadata:
    marker_names = [marker.name for marker in item.iter_markers()]
    metadata = metadata_for_node(item.nodeid, marker_names)
    if allure is None:
        return metadata

    _call_dynamic("parent_suite", metadata.parent_suite)
    _call_dynamic("suite", metadata.suite)
    _call_dynamic("sub_suite", metadata.sub_suite)
    _call_dynamic("epic", metadata.epic)
    _call_dynamic("feature", metadata.feature)
    _call_dynamic("story", metadata.story)
    _call_dynamic("severity", metadata.severity)
    _call_dynamic("owner", metadata.owner)

    for tag in metadata.tags:
        _call_dynamic("tag", tag)
    if metadata.test_case_id:
        _call_dynamic("parameter", "test_case_id", metadata.test_case_id)

    return metadata


def apply_metadata_to_result(result: dict[str, Any]) -> dict[str, Any]:
    identifier = str(result.get("fullName") or "")
    if not identifier:
        package = _label_values(result, "package")
        name = str(result.get("name") or "")
        identifier = f"{package[0]}#{name}" if package and name else name

    markers = _label_values(result, "tag")
    metadata = metadata_for_node(identifier, markers)

    labels = [label for label in result.get("labels", []) if label.get("name") not in CONTROLLED_LABELS]
    existing_tags = {label.get("value") for label in labels if label.get("name") == "tag"}

    labels.extend(
        [
            {"name": "parentSuite", "value": metadata.parent_suite},
            {"name": "suite", "value": metadata.suite},
            {"name": "subSuite", "value": metadata.sub_suite},
            {"name": "epic", "value": metadata.epic},
            {"name": "feature", "value": metadata.feature},
            {"name": "story", "value": metadata.story},
            {"name": "severity", "value": metadata.severity},
            {"name": "owner", "value": metadata.owner},
        ]
    )
    for tag in metadata.tags:
        if tag not in existing_tags:
            labels.append({"name": "tag", "value": tag})
            existing_tags.add(tag)
    result["labels"] = labels

    if metadata.test_case_id:
        parameters = result.setdefault("parameters", [])
        if not any(parameter.get("name") == "test_case_id" for parameter in parameters):
            parameters.append({"name": "test_case_id", "value": metadata.test_case_id})

    return result


def split_node_identifier(node_id: str) -> tuple[str, str]:
    raw = node_id.replace("\\", "/").split("[", 1)[0]
    if "#" in raw:
        module_name, test_name = raw.split("#", 1)
        path = module_name.replace(".", "/") + ".py"
        return path, test_name.split("::")[-1]
    if "::" in raw:
        path, test_name = raw.split("::", 1)
        return path, test_name.split("::")[-1]
    return raw, Path(raw).stem


def _web_metadata(file_name: str, test_name: str) -> AllureMetadata:
    if file_name == "test_login.py":
        return _metadata(
            parent_suite="eSuite Web",
            suite="Web",
            sub_suite="Login",
            epic="eSuite Web",
            feature="Authentication",
            story="Login to Dashboard",
            severity="critical",
            tags={"web", "login"},
        )
    if file_name == "test_create_company.py":
        story = "Step 1 Validation" if "step_one" in test_name else "Three Step Company Registration"
        return _metadata(
            parent_suite="eSuite Web",
            suite="Web",
            sub_suite="Company Registration",
            epic="eSuite Web",
            feature="Company Management",
            story=story,
            severity="critical" if "three_step" in test_name else "normal",
            tags={"web", "company-registration"},
        )
    if file_name == "test_company_registration_data.py":
        return _metadata(
            parent_suite="eSuite Web",
            suite="Web",
            sub_suite="Company Registration Data",
            epic="eSuite Web",
            feature="Test Data Mapping",
            story=_humanize_test_name(test_name),
            severity="normal",
            tags={"web", "test-data"},
        )
    if file_name == "test_deliberate_failure_evidence.py":
        return _metadata(
            parent_suite="eSuite Web",
            suite="Web",
            sub_suite="Failure Evidence",
            epic="eSuite Web",
            feature="Allure Evidence",
            story=_humanize_test_name(test_name),
            severity="normal",
            tags={"web", "evidence"},
        )
    return _metadata(
        parent_suite="eSuite Web",
        suite="Web",
        sub_suite=_humanize_file_name(file_name),
        epic="eSuite Web",
        feature="Web Automation",
        story=_humanize_test_name(test_name),
        severity="normal",
        tags={"web"},
    )


def _mobile_metadata(file_name: str, test_name: str) -> AllureMetadata:
    if file_name == "test_mobile_login.py":
        return _metadata(
            parent_suite="eWork SFA",
            suite="Mobile",
            sub_suite="Login",
            epic="eWork SFA",
            feature="Authentication",
            story="Login to Dashboard",
            severity="critical",
            tags={"mobile", "login"},
        )
    if file_name == "test_mobile_create_customer.py":
        live_flow = test_name == "test_ework_create_customer_appears_with_correct_data"
        return _metadata(
            parent_suite="eWork SFA",
            suite="Mobile",
            sub_suite="Customer Creation",
            epic="eWork SFA",
            feature="Customer Management",
            story="Create Customer and Verify Data" if live_flow else _humanize_test_name(test_name),
            severity="critical" if live_flow else "normal",
            tags={"mobile", "customer-creation"},
        )
    return _metadata(
        parent_suite="eWork SFA",
        suite="Mobile",
        sub_suite="Mobile Foundation",
        epic="eWork SFA",
        feature="Runtime Guardrails",
        story=_humanize_test_name(test_name),
        severity="normal",
        tags={"mobile", "foundation"},
    )


def _ai_metadata(file_name: str, test_name: str) -> AllureMetadata:
    if file_name == "test_test_data.py":
        return _metadata(
            parent_suite="AI QA Support",
            suite="AI",
            sub_suite="AI Test Data",
            epic="AI QA Support",
            feature="Test Data Generation",
            story=_humanize_test_name(test_name),
            severity="normal",
            tags={"ai", "test-data"},
        )
    return _metadata(
        parent_suite="AI QA Support",
        suite="AI",
        sub_suite="AI Failure Triage",
        epic="AI QA Support",
        feature="Failure Triage",
        story=_humanize_test_name(test_name),
        severity="normal",
        tags={"ai", "failure-triage"},
    )


def _metadata(
    *,
    parent_suite: str,
    suite: str,
    sub_suite: str,
    epic: str,
    feature: str,
    story: str,
    severity: str,
    tags: set[str],
) -> AllureMetadata:
    return AllureMetadata(
        parent_suite=parent_suite,
        suite=suite,
        sub_suite=sub_suite,
        epic=epic,
        feature=feature,
        story=story,
        severity=severity,
        owner="qa-automation",
        tags=tuple(sorted(tags)),
    )


def _call_dynamic(method: str, *args: str) -> None:
    dynamic = getattr(allure, "dynamic", None) if allure is not None else None
    function = getattr(dynamic, method, None)
    if not callable(function):
        return
    try:
        function(*args)
    except Exception:
        return


def _label_values(result: dict[str, Any], name: str) -> list[str]:
    labels = result.get("labels", [])
    return [str(label.get("value")) for label in labels if label.get("name") == name and label.get("value")]


def _humanize_file_name(file_name: str) -> str:
    stem = Path(file_name).stem
    if stem.startswith("test_"):
        stem = stem[5:]
    return _humanize(stem)


def _humanize_test_name(test_name: str) -> str:
    if test_name.startswith("test_"):
        test_name = test_name[5:]
    return _humanize(test_name)


def _humanize(value: str) -> str:
    text = value.replace("_", " ").replace("-", " ").strip().title()
    replacements = {
        "Ai": "AI",
        "Api": "API",
        "Db": "DB",
        "Id": "ID",
        "Ui": "UI",
        "Adb": "ADB",
        "Cli": "CLI",
        "Ework": "eWork",
        "Esuite": "eSuite",
    }
    for before, after in replacements.items():
        text = re.sub(rf"\b{before}\b", after, text)
    return text
