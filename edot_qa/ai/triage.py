from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Protocol

from edot_qa.ai.test_data import extract_gemini_text
from edot_qa.config import Settings, load_settings


SCRIPT_ENVIRONMENT_DEFECT = "script/environment defect"
PRODUCT_BUG = "product bug"
FLAKY = "flaky"

FAILURE_STATUSES = {"failed", "broken"}

LOCATOR_PATTERNS = (
    "strict mode violation",
    "resolved to",
    "multiple elements",
    "ambiguous locator",
    "locator resolved",
    "selector matched",
    "more than one element",
)
PRECONDITION_PATTERNS = (
    "precondition",
    "missing",
    "not installed",
    "not on path",
    "no devices",
    "device not found",
    "storage_state",
    "credential",
    "authentication required",
    "login required",
    "maestro cli",
    "adb-visible",
)
EXPECTED_VALUE_PATTERNS = (
    "expected value is wrong",
    "expected value invalid",
    "expected value was incorrect",
    "test case expected value mismatch",
    "expected data is stale",
    "expected data not in test case",
)
ASSERTION_PATTERNS = (
    "assertionerror",
    "assert ",
    "expected",
    "actual",
    "to have text",
    "not equal",
    "!=",
)
EXCEPTION_PATTERNS = (
    "timeouterror",
    "timeout",
    "element not found",
    "not found",
    "not visible",
    "target closed",
    "browser has been closed",
    "exception",
    "error:",
    "playwright",
    "maestro",
    "adb",
)
DANGEROUS_AI_NOTE_PATTERNS = (
    "weaken assertion",
    "skip assertion",
    "rewrite assertion",
    "swallow failure",
    "change expected",
    "expected to actual",
    "auto-file",
    "auto close",
    "auto-close",
)


@dataclass(frozen=True)
class AllureStep:
    name: str
    status: str | None
    message: str | None = None


@dataclass(frozen=True)
class AllureFailure:
    name: str
    full_name: str
    status: str
    history_id: str
    message: str
    trace: str
    steps: tuple[AllureStep, ...]
    attachments: tuple[str, ...]
    labels: dict[str, str]
    source_path: Path

    @property
    def key(self) -> str:
        return self.history_id or self.full_name or self.name


@dataclass(frozen=True)
class TriageVerdict:
    failure: AllureFailure
    verdict: str
    matched_rule: str
    evidence: tuple[str, ...]
    ai_note: str | None = None


@dataclass(frozen=True)
class TriageReport:
    results_dir: Path
    output_path: Path
    verdicts: tuple[TriageVerdict, ...]
    markdown: str

    @property
    def summary(self) -> Counter[str]:
        return Counter(verdict.verdict for verdict in self.verdicts)


class TriageAIProvider(Protocol):
    def summarize(self, prompt: str, *, model: str, max_output_tokens: int) -> str:
        """Return a concise human-review note."""


class GeminiTriageProvider:
    api_url_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def summarize(self, prompt: str, *, model: str, max_output_tokens: int) -> str:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
            },
        }
        request = urllib.request.Request(
            self.api_url_template.format(model=model, api_key=self.api_key),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError(f"Gemini API request failed: {error}") from error
        return extract_gemini_text(body)


def parse_allure_results(results_dir: Path) -> list[AllureFailure]:
    failures: list[AllureFailure] = []
    if not results_dir.exists():
        return failures

    for path in sorted(results_dir.glob("*-result.json")):
        payload = _read_json(path)
        if payload is None or payload.get("status") not in FAILURE_STATUSES:
            continue

        details = payload.get("statusDetails") or {}
        labels = {
            str(item.get("name")): str(item.get("value"))
            for item in payload.get("labels", [])
            if isinstance(item, dict) and item.get("name") and item.get("value")
        }
        failures.append(
            AllureFailure(
                name=str(payload.get("name") or path.stem),
                full_name=str(payload.get("fullName") or payload.get("name") or path.stem),
                status=str(payload.get("status") or "unknown"),
                history_id=str(payload.get("historyId") or payload.get("testCaseId") or ""),
                message=str(details.get("message") or ""),
                trace=str(details.get("trace") or ""),
                steps=tuple(_flatten_steps(payload.get("steps", []))),
                attachments=tuple(_attachment_names(payload)),
                labels=labels,
                source_path=path,
            )
        )
    return failures


def classify_failure(failure: AllureFailure, previous_outcomes: Iterable[str] = ()) -> TriageVerdict:
    text = _combined_failure_text(failure)
    precondition_text = _precondition_failure_text(failure)
    evidence = [_failure_type_evidence(failure, text)]

    has_locator_signal = _contains_any(text, LOCATOR_PATTERNS)
    has_precondition_signal = _contains_any(precondition_text, PRECONDITION_PATTERNS) or _has_failed_setup_step(failure)
    has_expected_value_signal = _contains_any(text, EXPECTED_VALUE_PATTERNS)
    looks_like_assertion = _contains_any(text, ASSERTION_PATTERNS) or failure.status == "failed"
    looks_like_exception = failure.status == "broken" or (
        _contains_any(text, EXCEPTION_PATTERNS) and "assertionerror" not in text
    )

    if looks_like_exception and not (has_locator_signal or has_precondition_signal or has_expected_value_signal):
        evidence.append(_short_text_evidence(failure))
        return TriageVerdict(
            failure=failure,
            verdict=SCRIPT_ENVIRONMENT_DEFECT,
            matched_rule="1. exception/assertion classification",
            evidence=tuple(evidence),
        )

    if has_locator_signal:
        evidence.append("Locator evidence says selector resolved ambiguously or not to a unique intended element.")
        evidence.append(_short_text_evidence(failure))
        return TriageVerdict(
            failure=failure,
            verdict=SCRIPT_ENVIRONMENT_DEFECT,
            matched_rule="2. locator uniqueness",
            evidence=tuple(evidence),
        )

    if has_precondition_signal:
        evidence.append("Precondition evidence shows setup, credential, device, auth, or prior-step problem.")
        evidence.extend(_failed_step_evidence(failure))
        evidence.append(_short_text_evidence(failure))
        return TriageVerdict(
            failure=failure,
            verdict=SCRIPT_ENVIRONMENT_DEFECT,
            matched_rule="3. preconditions",
            evidence=tuple(_dedupe(evidence)),
        )

    if has_expected_value_signal:
        evidence.append("Expected-value evidence says test expectation or test case data is invalid or stale.")
        evidence.append(_short_text_evidence(failure))
        return TriageVerdict(
            failure=failure,
            verdict=SCRIPT_ENVIRONMENT_DEFECT,
            matched_rule="4. expected value check",
            evidence=tuple(evidence),
        )

    normalized_outcomes = {outcome.lower() for outcome in previous_outcomes if outcome}
    if normalized_outcomes & FAILURE_STATUSES and "passed" in normalized_outcomes:
        evidence.append("Same test has both passed and failed/broken outcomes in available Allure results.")
        return TriageVerdict(
            failure=failure,
            verdict=FLAKY,
            matched_rule="5. reproducibility",
            evidence=tuple(evidence),
        )

    if looks_like_assertion:
        evidence.append("Assertion reached after deterministic checks found no locator, precondition, or expected-value defect.")
        evidence.append("No pass/fail mix found in available Allure results; verdict remains human-review proposal.")
        return TriageVerdict(
            failure=failure,
            verdict=PRODUCT_BUG,
            matched_rule="5. reproducibility",
            evidence=tuple(evidence),
        )

    evidence.append("Failure did not expose enough product-state evidence; safest verdict is script/environment.")
    return TriageVerdict(
        failure=failure,
        verdict=SCRIPT_ENVIRONMENT_DEFECT,
        matched_rule="1. exception/assertion classification",
        evidence=tuple(evidence),
    )


def triage_allure_results(
    results_dir: Path,
    output_path: Path,
    *,
    settings: Settings | None = None,
    ai_provider: TriageAIProvider | None = None,
    use_ai: bool = True,
) -> TriageReport:
    failures = parse_allure_results(results_dir)
    outcomes = _outcomes_by_key(results_dir)
    verdicts = [
        classify_failure(failure, outcomes.get(failure.key, (failure.status,)))
        for failure in failures
    ]
    if use_ai:
        verdicts = _add_ai_notes(verdicts, settings or load_settings(), ai_provider)

    markdown = render_markdown(verdicts, results_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return TriageReport(
        results_dir=results_dir,
        output_path=output_path,
        verdicts=tuple(verdicts),
        markdown=markdown,
    )


def render_markdown(verdicts: Iterable[TriageVerdict], results_dir: Path) -> str:
    rendered = list(verdicts)
    lines = [
        "# eDOT AI Failure Triage Report",
        "",
        f"Allure results: `{results_dir}`",
        "",
        "Guardrails: human-review proposal only; no assertion changes; no swallowed failures; no expected-to-actual edits; no bug filing or closing.",
        "",
        "Decision order: 1 exception/assertion, 2 locator uniqueness, 3 preconditions, 4 expected value, 5 reproducibility.",
        "",
    ]
    if not rendered:
        lines.extend(["No failed or broken Allure test results found.", ""])
        return "\n".join(lines)

    counts = Counter(verdict.verdict for verdict in rendered)
    lines.extend(
        [
            "## Summary",
            "",
            f"- {SCRIPT_ENVIRONMENT_DEFECT}: {counts[SCRIPT_ENVIRONMENT_DEFECT]}",
            f"- {PRODUCT_BUG}: {counts[PRODUCT_BUG]}",
            f"- {FLAKY}: {counts[FLAKY]}",
            "",
            "## Failures",
            "",
        ]
    )
    for index, verdict in enumerate(rendered, start=1):
        failure = verdict.failure
        lines.extend(
            [
                f"### {index}. {failure.name}",
                "",
                f"- Verdict: {verdict.verdict}",
                f"- Matched rule: {verdict.matched_rule}",
                f"- Status: {failure.status}",
                f"- Source: `{failure.source_path}`",
                "- Evidence:",
            ]
        )
        lines.extend(f"  - {item}" for item in verdict.evidence)
        if verdict.ai_note:
            lines.extend(["- AI note:", *[f"  - {line}" for line in verdict.ai_note.splitlines() if line.strip()]])
        lines.append("")
    return "\n".join(lines)


def build_triage_prompt(verdict: TriageVerdict) -> str:
    evidence = "\n".join(f"- {item}" for item in verdict.evidence[:8])
    return (
        "Review deterministic QA failure triage. Do not change verdict. "
        "Do not weaken, skip, or rewrite assertions. Do not swallow failures. "
        "Do not change expected values to actual values. Do not auto-file or auto-close bugs. "
        "Return at most 3 concise bullets for human review.\n"
        f"Test: {verdict.failure.name}\n"
        f"Status: {verdict.failure.status}\n"
        f"Verdict: {verdict.verdict}\n"
        f"Matched rule: {verdict.matched_rule}\n"
        f"Evidence:\n{evidence}"
    )


def _add_ai_notes(
    verdicts: list[TriageVerdict],
    settings: Settings,
    ai_provider: TriageAIProvider | None,
) -> list[TriageVerdict]:
    provider = ai_provider or _default_ai_provider(settings)
    if provider is None:
        return verdicts

    updated: list[TriageVerdict] = []
    for verdict in verdicts:
        try:
            note = provider.summarize(
                build_triage_prompt(verdict),
                model=settings.gemini_triage_model,
                max_output_tokens=settings.ai_triage_max_output_tokens,
            )
        except RuntimeError as error:
            updated.append(
                replace(verdict, evidence=verdict.evidence + (f"AI note unavailable: {error}",))
            )
            continue

        safe_note = _sanitize_ai_note(note)
        if safe_note is None:
            updated.append(
                replace(
                    verdict,
                    evidence=verdict.evidence
                    + ("AI note rejected because it violated triage guardrails.",),
                )
            )
            continue
        updated.append(replace(verdict, ai_note=safe_note))
    return updated


def _default_ai_provider(settings: Settings) -> TriageAIProvider | None:
    if not settings.gemini_api_key:
        return None
    return GeminiTriageProvider(settings.gemini_api_key)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _flatten_steps(steps: Iterable[dict], prefix: str = "") -> list[AllureStep]:
    flattened: list[AllureStep] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        name = str(step.get("name") or "<unnamed step>")
        status = step.get("status")
        details = step.get("statusDetails") or {}
        full_name = f"{prefix}{name}" if not prefix else f"{prefix} > {name}"
        flattened.append(
            AllureStep(
                name=full_name,
                status=str(status) if status else None,
                message=str(details.get("message") or ""),
            )
        )
        flattened.extend(_flatten_steps(step.get("steps", []), full_name))
    return flattened


def _attachment_names(payload: dict) -> list[str]:
    names: list[str] = []
    for attachment in payload.get("attachments", []):
        if isinstance(attachment, dict) and attachment.get("name"):
            names.append(str(attachment["name"]))
    for step in payload.get("steps", []):
        names.extend(_step_attachment_names(step))
    return names


def _step_attachment_names(step: dict) -> list[str]:
    names: list[str] = []
    if not isinstance(step, dict):
        return names
    for attachment in step.get("attachments", []):
        if isinstance(attachment, dict) and attachment.get("name"):
            names.append(str(attachment["name"]))
    for child in step.get("steps", []):
        names.extend(_step_attachment_names(child))
    return names


def _outcomes_by_key(results_dir: Path) -> dict[str, tuple[str, ...]]:
    outcomes: defaultdict[str, list[str]] = defaultdict(list)
    if not results_dir.exists():
        return {}
    for path in sorted(results_dir.glob("*-result.json")):
        payload = _read_json(path)
        if payload is None:
            continue
        key = str(payload.get("historyId") or payload.get("testCaseId") or payload.get("fullName") or payload.get("name") or "")
        status = payload.get("status")
        if key and status:
            outcomes[key].append(str(status))
    return {key: tuple(values) for key, values in outcomes.items()}


def _combined_failure_text(failure: AllureFailure) -> str:
    parts = [
        failure.name,
        failure.full_name,
        failure.status,
        failure.message,
        failure.trace,
        *failure.attachments,
    ]
    for step in failure.steps:
        parts.extend([step.name, step.status or "", step.message or ""])
    return "\n".join(parts).lower()


def _precondition_failure_text(failure: AllureFailure) -> str:
    parts = [failure.message]
    for step in failure.steps:
        if step.status in FAILURE_STATUSES:
            parts.extend([step.name, step.message or ""])
    return "\n".join(parts).lower()


def _contains_any(text: str, patterns: Iterable[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def _failure_type_evidence(failure: AllureFailure, text: str) -> str:
    looks_like_exception = failure.status == "broken" or (
        _contains_any(text, EXCEPTION_PATTERNS) and "assertionerror" not in text
    )
    if looks_like_exception:
        return "Step 1: failure type appears to be exception or environment error."
    if _contains_any(text, ASSERTION_PATTERNS) or failure.status == "failed":
        return "Step 1: failure type appears to be failed assertion."
    return "Step 1: failure type is unclear from Allure status details."


def _has_failed_setup_step(failure: AllureFailure) -> bool:
    for step in failure.steps:
        if step.status not in FAILURE_STATUSES:
            continue
        name = step.name.lower()
        if not _contains_any(name, ("assert", "verify", "expect")):
            return True
    return False


def _failed_step_evidence(failure: AllureFailure) -> tuple[str, ...]:
    evidence = []
    for step in failure.steps:
        if step.status in FAILURE_STATUSES:
            evidence.append(f"Prior failing step: {step.name}")
    return tuple(evidence)


def _short_text_evidence(failure: AllureFailure) -> str:
    text = failure.message or failure.trace or "No Allure status message or trace present."
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) > 280:
        compact = f"{compact[:277]}..."
    return f"Allure detail: {compact}"


def _sanitize_ai_note(note: str) -> str | None:
    compact = re.sub(r"\s+", " ", note).strip()
    if not compact:
        return None
    lowered = compact.lower()
    if any(pattern in lowered for pattern in DANGEROUS_AI_NOTE_PATTERNS):
        return None
    return compact[:1200]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
