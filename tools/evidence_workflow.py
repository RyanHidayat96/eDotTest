from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
DELIBERATE_FAILURE_ENV = "EDOT_DELIBERATE_FAILURE"
DELIBERATE_FAILURE_MODE = "wrong_locator"
EVIDENCE_DIR = ROOT_DIR / "evidence"
WEB_RESULTS_DIR = ROOT_DIR / "reports" / "allure-results"
WEB_REPORT_DIR = EVIDENCE_DIR / "web-allure"
DELIBERATE_RESULTS_DIR = ROOT_DIR / "reports" / "allure-results-deliberate"
DELIBERATE_REPORT_DIR = EVIDENCE_DIR / "deliberate-allure"
DELIBERATE_TRIAGE_REPORT = EVIDENCE_DIR / "triage" / "triage-report.md"

SENSITIVE_KEY_RE = re.compile(
    r"(?:API_KEY|PASSWORD|TOKEN|SECRET|AUTHORIZATION|COOKIE|CREDENTIAL|COMPANY_CODE|COMPANY_ID|EMAIL)",
    re.IGNORECASE,
)
TOKEN_PATTERNS = (
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("Gemini/Google API token", re.compile(r"\bAQ\.[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b")),
)
RAW_SECRET_HEADER_RE = re.compile(r"\b(?:authorization|cookie|set-cookie)\s*:", re.IGNORECASE)
TEXT_SUFFIXES = {
    ".csv",
    ".env",
    ".html",
    ".json",
    ".md",
    ".properties",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
FORBIDDEN_EVIDENCE_NAMES = {".env", ".npmrc", ".pypirc", ".netrc", "storage_state.json", "storage-state.json"}
FORBIDDEN_EVIDENCE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".crt"}
GENERATED_TOP_LEVEL_DIRS = {"reports", "evidence"}


@dataclass(frozen=True)
class EvidenceCommand:
    name: str
    command: tuple[str, ...]
    env: tuple[tuple[str, str], ...] = ()
    expected_failure: bool = False
    continue_after_failure: bool = False


@dataclass(frozen=True)
class EvidencePlan:
    name: str
    clean_paths: tuple[Path, ...]
    commands: tuple[EvidenceCommand, ...]


@dataclass(frozen=True)
class EvidenceFinding:
    path: str
    reason: str


def deliberate_failure_enabled(mode: str = DELIBERATE_FAILURE_MODE, env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return source.get(DELIBERATE_FAILURE_ENV, "").strip().lower() == mode


def build_full_web_plan() -> EvidencePlan:
    return EvidencePlan(
        name="full-web",
        clean_paths=(WEB_RESULTS_DIR, WEB_REPORT_DIR),
        commands=(
            EvidenceCommand(
                name="run full required web scenarios",
                command=(
                    _python(),
                    "-m",
                    "pytest",
                    "tests/web/test_login.py",
                    "tests/web/test_create_company.py",
                    "--alluredir",
                    _rel(WEB_RESULTS_DIR),
                    "--clean-alluredir",
                ),
                continue_after_failure=True,
            ),
            EvidenceCommand(
                name="generate preserved web Allure report",
                command=(
                    _python(),
                    "tools/generate_allure_report.py",
                    "--results-dir",
                    _rel(WEB_RESULTS_DIR),
                    "--report-dir",
                    _rel(WEB_REPORT_DIR),
                ),
            ),
            EvidenceCommand(
                name="scan preserved evidence for secrets",
                command=(_python(), "tools/evidence_workflow.py", "scan", "--evidence-dir", _rel(EVIDENCE_DIR)),
            ),
        ),
    )


def build_deliberate_failure_plan() -> EvidencePlan:
    return EvidencePlan(
        name="deliberate-failure",
        clean_paths=(DELIBERATE_RESULTS_DIR, DELIBERATE_REPORT_DIR, DELIBERATE_TRIAGE_REPORT.parent),
        commands=(
            EvidenceCommand(
                name="run isolated deliberate wrong-locator failure",
                command=(
                    _python(),
                    "-m",
                    "pytest",
                    "tests/web/test_deliberate_failure_evidence.py::test_deliberate_wrong_locator_failure_records_real_allure_failure",
                    "--alluredir",
                    _rel(DELIBERATE_RESULTS_DIR),
                    "--clean-alluredir",
                    "-q",
                ),
                env=((DELIBERATE_FAILURE_ENV, DELIBERATE_FAILURE_MODE),),
                expected_failure=True,
            ),
            EvidenceCommand(
                name="triage deliberate Allure failure",
                command=(
                    _python(),
                    "tools/triage_allure_failures.py",
                    "--results-dir",
                    _rel(DELIBERATE_RESULTS_DIR),
                    "--output",
                    _rel(DELIBERATE_TRIAGE_REPORT),
                ),
            ),
            EvidenceCommand(
                name="generate preserved deliberate-failure Allure report",
                command=(
                    _python(),
                    "tools/generate_allure_report.py",
                    "--results-dir",
                    _rel(DELIBERATE_RESULTS_DIR),
                    "--report-dir",
                    _rel(DELIBERATE_REPORT_DIR),
                ),
            ),
            EvidenceCommand(
                name="scan preserved evidence for secrets",
                command=(_python(), "tools/evidence_workflow.py", "scan", "--evidence-dir", _rel(EVIDENCE_DIR)),
            ),
        ),
    )


def validate_generated_path(path: Path, *, root: Path = ROOT_DIR) -> Path:
    resolved_root = root.resolve()
    resolved = _resolve(path, resolved_root)
    relative = _relative_to_root(resolved, resolved_root)
    if not relative.parts:
        raise ValueError("generated path must not be project root")
    if relative.parts[0] not in GENERATED_TOP_LEVEL_DIRS:
        raise ValueError(f"generated path must stay under reports/ or evidence/: {relative.as_posix()}")
    if any(part in {".git", ".codex", ".agents", ".venv"} for part in relative.parts):
        raise ValueError(f"generated path targets unsafe directory: {relative.as_posix()}")
    return resolved


def scan_evidence_dir(
    evidence_dir: Path,
    *,
    root: Path = ROOT_DIR,
    secret_values: Iterable[str] | None = None,
) -> list[EvidenceFinding]:
    resolved_root = root.resolve()
    resolved_dir = _resolve(evidence_dir, resolved_root)
    _relative_to_root(resolved_dir, resolved_root)
    if not resolved_dir.exists():
        return []
    if not resolved_dir.is_dir():
        return [EvidenceFinding(_safe_rel(resolved_dir, resolved_root), "evidence path is not a directory")]

    secrets = tuple(secret_values) if secret_values is not None else known_secret_values(resolved_root)
    findings: list[EvidenceFinding] = []
    for path in sorted(resolved_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = _safe_rel(path, resolved_root)
        forbidden = _forbidden_evidence_file(Path(relative))
        if forbidden:
            findings.append(EvidenceFinding(relative, forbidden))
            continue
        findings.extend(_scan_file(path, relative, secrets))
    return findings


def known_secret_values(root: Path = ROOT_DIR, env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    values: list[str] = []
    source = os.environ if env is None else env
    for key, value in source.items():
        if _is_sensitive_key(key) and not _is_placeholder(value):
            values.append(value)
    env_path = root / ".env"
    if env_path.is_file():
        for key, value in _parse_env_file(env_path).items():
            if _is_sensitive_key(key) and not _is_placeholder(value):
                values.append(value)
    return tuple(sorted(set(values), key=len, reverse=True))


def run_plan(plan: EvidencePlan, *, dry_run: bool) -> int:
    for path in plan.clean_paths:
        validate_generated_path(path)

    if dry_run:
        print(f"plan={plan.name}")
        print("prepare=evidence/README.md")
        for path in plan.clean_paths:
            print(f"clean={_rel(path)}")
        for step in plan.commands:
            env_prefix = " ".join(f"{key}={value}" for key, value in step.env)
            command = _display_command(step.command)
            expected = " expected_failure=true" if step.expected_failure else ""
            print(f"step={step.name}{expected}")
            print(f"command={env_prefix + ' ' if env_prefix else ''}{command}")
        return 0

    _write_evidence_readme()
    for path in plan.clean_paths:
        _clean_generated_path(path)
    exit_code = 0
    for step in plan.commands:
        result = _run_command(step)
        if step.expected_failure:
            if result.returncode == 0:
                print(f"FAIL {step.name}: deliberate failure did not fail")
                return 1
            if not _allure_failure_result_exists(DELIBERATE_RESULTS_DIR):
                print(f"FAIL {step.name}: no failed Allure result was written")
                return 1
            continue
        if result.returncode != 0:
            if step.continue_after_failure:
                exit_code = exit_code or result.returncode
                continue
            return result.returncode
    return exit_code


def validate_paths(plans: Sequence[EvidencePlan]) -> list[str]:
    messages: list[str] = []
    for plan in plans:
        for path in plan.clean_paths:
            resolved = validate_generated_path(path)
            messages.append(f"{plan.name}:{_rel(resolved)}")
    return messages


def render_findings(findings: Iterable[EvidenceFinding]) -> str:
    return "\n".join(f"FAIL {finding.path}: {finding.reason}" for finding in findings)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and run safe eDOT evidence workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    full_web = subparsers.add_parser("full-web", help="Run required web scenarios and preserve Allure evidence.")
    full_web.add_argument("--dry-run", action="store_true", help="Validate paths and print commands only.")

    deliberate = subparsers.add_parser("deliberate-failure", help="Run isolated wrong-locator evidence and triage.")
    deliberate.add_argument("--dry-run", action="store_true", help="Validate paths and print commands only.")

    scan = subparsers.add_parser("scan", help="Scan evidence files for secrets without printing values.")
    scan.add_argument("--evidence-dir", type=Path, default=EVIDENCE_DIR)

    validate = subparsers.add_parser("validate-paths", help="Validate generated evidence paths.")
    validate.add_argument("--plan", choices=("all", "full-web", "deliberate-failure"), default="all")

    args = parser.parse_args()
    if args.command == "full-web":
        return run_plan(build_full_web_plan(), dry_run=args.dry_run)
    if args.command == "deliberate-failure":
        return run_plan(build_deliberate_failure_plan(), dry_run=args.dry_run)
    if args.command == "scan":
        findings = scan_evidence_dir(args.evidence_dir)
        if findings:
            print(render_findings(findings))
            return 1
        print("Evidence safety scan passed.")
        return 0
    if args.command == "validate-paths":
        plans = []
        if args.plan in {"all", "full-web"}:
            plans.append(build_full_web_plan())
        if args.plan in {"all", "deliberate-failure"}:
            plans.append(build_deliberate_failure_plan())
        for message in validate_paths(plans):
            print(f"OK {message}")
        return 0
    raise AssertionError(args.command)


def _python() -> str:
    return sys.executable or "python"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
    except ValueError:
        return str(path)


def _resolve(path: Path, root: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _relative_to_root(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"path must stay inside project root: {path}") from error


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _clean_generated_path(path: Path) -> None:
    resolved = validate_generated_path(path)
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


def _run_command(step: EvidenceCommand) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(dict(step.env))
    print(f"[Evidence] {step.name}")
    return subprocess.run(step.command, cwd=ROOT_DIR, env=env, check=False, text=True)


def _allure_failure_result_exists(results_dir: Path) -> bool:
    for result_path in sorted(results_dir.glob("*-result.json")):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("status") in {"failed", "broken"}:
            return True
    return False


def _display_command(command: Sequence[str]) -> str:
    display = ["python" if index == 0 and value == _python() else value for index, value in enumerate(command)]
    return subprocess.list2cmdline(display)


def _write_evidence_readme() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Execution Evidence",
                "",
                "Generated evidence belongs here after the final execution step.",
                "",
                "- `web-allure/`: Allure HTML report from the required web scenarios.",
                "- `deliberate-allure/`: Allure HTML report from the isolated deliberate-failure run.",
                "- `triage/triage-report.md`: human-review triage proposal for the deliberate failure.",
                "",
                "Do not place `.env`, storage state, cookies, API keys, passwords, or raw secret headers here.",
                "Run `npm run evidence:scan` before packaging or sharing evidence.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _forbidden_evidence_file(relative: Path) -> str | None:
    parts = [part.lower() for part in relative.parts]
    name = relative.name.lower()
    suffix = relative.suffix.lower()
    if name in FORBIDDEN_EVIDENCE_NAMES:
        return "secret/session file must not be preserved as evidence"
    if suffix in FORBIDDEN_EVIDENCE_SUFFIXES:
        return "key/certificate file must not be preserved as evidence"
    if any(token in name for token in ("storage_state", "storage-state", "cookie", "session", "auth_state")):
        return "auth/session artifact must not be preserved as evidence"
    if any(part in {".git", ".codex", ".agents"} for part in parts):
        return "local tool metadata must not be preserved as evidence"
    return None


def _scan_file(path: Path, relative: str, secret_values: tuple[str, ...]) -> list[EvidenceFinding]:
    findings: list[EvidenceFinding] = []
    try:
        data = path.read_bytes()
    except OSError:
        return [EvidenceFinding(relative, "could not inspect evidence file")]

    for secret in secret_values:
        if secret and secret.encode("utf-8", errors="ignore") in data:
            findings.append(EvidenceFinding(relative, "known secret value detected"))
            break

    if path.suffix.lower() not in TEXT_SUFFIXES:
        return findings
    text = data.decode("utf-8", errors="ignore")
    for reason, pattern in TOKEN_PATTERNS:
        if pattern.search(text):
            findings.append(EvidenceFinding(relative, f"{reason} detected"))
            break
    if RAW_SECRET_HEADER_RE.search(text):
        findings.append(EvidenceFinding(relative, "raw secret header detected"))
    return findings


def _is_sensitive_key(key: str) -> bool:
    return bool(SENSITIVE_KEY_RE.search(key))


def _is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip("'\"")
    if len(cleaned) < 4:
        return True
    lowered = cleaned.lower()
    return lowered in {"none", "null", "true", "false"} or any(
        token in lowered for token in ("example", "placeholder", "redacted", "missing", "dummy", "changeme")
    )


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


if __name__ == "__main__":
    raise SystemExit(main())
