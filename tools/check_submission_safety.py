from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_GITIGNORE_LINES = {
    ".env",
    ".env.*",
    "!.env.example",
    "artifacts/",
    "reports/",
    "allure-results/",
    "allure-report/",
    "evidence/web-allure/",
    "evidence/deliberate-allure/",
    "evidence/triage/",
    "*.key",
    "*.pem",
}

RUNTIME_DIR_PARTS = {
    "artifacts",
    "reports",
    "allure-results",
    "allure-report",
    "playwright-report",
    "test-results",
    "maestro-output",
    ".maestro",
    ".allure",
    ".playwright",
}

SECRET_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".crt"}
SECRET_FILE_NAMES = {".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519"}
TEXT_SUFFIXES = {".csv", ".env", ".example", ".ini", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
TEXT_NAMES = {".gitignore", "Dockerfile"}

SECRET_KEY_RE = re.compile(
    r"(?:API_KEY|PASSWORD|TOKEN|SECRET|AUTHORIZATION|COOKIE|CREDENTIAL|COMPANY_CODE|PRIVATE_KEY)",
    re.IGNORECASE,
)
ENV_ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*([^#]*)")
MAPPING_ASSIGNMENT_RE = re.compile(
    r"""^\s*["']?([A-Z][A-Z0-9_]*(?:API_KEY|PASSWORD|TOKEN|SECRET|AUTHORIZATION|COOKIE|CREDENTIAL|COMPANY_CODE|PRIVATE_KEY)[A-Z0-9_]*)["']?\s*[:=]\s*["']?([^"',\s#}]+)""",
)
TOKEN_PATTERNS = (
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("Gemini/Google API token", re.compile(r"\bAQ\.[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b")),
)


@dataclass(frozen=True)
class Finding:
    path: str
    reason: str


def _normalise(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _git_files(root: Path) -> tuple[list[str], bool]:
    commands = (
        ["git", "ls-files", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    )
    files: list[str] = []
    for command in commands:
        result = subprocess.run(command, cwd=root, capture_output=True, check=False)
        if result.returncode != 0:
            return [], False
        files.extend(
            item.decode("utf-8", errors="replace")
            for item in result.stdout.split(b"\0")
            if item
        )
    return sorted(set(_normalise(item) for item in files)), True


def _walk_files(root: Path) -> list[str]:
    files: list[str] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name != ".git"]
        current_path = Path(current)
        for name in names:
            files.append(_normalise(str((current_path / name).relative_to(root))))
    return sorted(files)


def _candidate_files(root: Path, tracked_files: list[str] | None = None) -> list[str]:
    if tracked_files is not None:
        return sorted(set(_normalise(item) for item in tracked_files))

    files, git_available = _git_files(root)
    if git_available:
        return files
    return _walk_files(root)


def _is_sensitive_key(key: str) -> bool:
    upper = key.upper()
    if upper.endswith(
        (
            "_FIELD_ID",
            "_BUTTON_ID",
            "_MENU_ID",
            "_SCREEN_TEXT",
            "_TEXT",
            "_MODEL",
            "_TOKENS",
            "_TOKEN_LIMIT",
            "_MAX_TOKENS",
            "_URL",
            "_DIR",
            "_PATH",
            "_COMMAND",
            "_CLI",
            "_APP_ID",
            "_BASE_URL",
        )
    ):
        return False
    return bool(SECRET_KEY_RE.search(upper))


def _is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip(",").strip().strip("'\"")
    if not cleaned:
        return True
    if cleaned.startswith(("<", "${", "%", "os.getenv(", "None")):
        return True
    lowered = cleaned.lower()
    if lowered in {"none", "null", "false", "true", "0"}:
        return True
    safe_fragments = (
        "placeholder",
        "example",
        "dummy",
        "test-only",
        "secure environment value",
        "redacted",
        "missing",
        "changeme",
        "todo",
    )
    return any(fragment in lowered for fragment in safe_fragments)


def _is_text_file(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def _check_gitignore(root: Path) -> list[Finding]:
    path = root / ".gitignore"
    if not path.exists():
        return [Finding(".gitignore", "required ignore file is missing")]
    lines = {
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    return [
        Finding(".gitignore", f"missing required ignore rule: {rule}")
        for rule in sorted(REQUIRED_GITIGNORE_LINES - lines)
    ]


def _check_env_example(root: Path) -> list[Finding]:
    path = root / ".env.example"
    if not path.exists():
        return [Finding(".env.example", "required safe template is missing")]

    findings: list[Finding] = []
    for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        match = ENV_ASSIGNMENT_RE.match(line)
        if not match:
            continue
        key, value = match.groups()
        if _is_sensitive_key(key) and not _is_placeholder(value):
            findings.append(Finding(".env.example", f"secret-like template value must be blank at line {index}"))
    return findings


def _check_forbidden_path(rel_path: str) -> Finding | None:
    normalised = _normalise(rel_path)
    lowered = normalised.lower()
    parts = lowered.split("/")
    name = parts[-1]
    suffix = Path(name).suffix.lower()

    if any(part == ".env" or (part.startswith(".env.") and part != ".env.example") for part in parts):
        return Finding(normalised, "runtime environment file must not be submitted")
    if any(part in RUNTIME_DIR_PARTS for part in parts):
        return Finding(normalised, "runtime artifact/report path must not be submitted")
    if lowered.startswith(("evidence/web-allure/", "evidence/deliberate-allure/", "evidence/triage/")):
        return Finding(normalised, "generated evidence artifact must not be submitted")
    if suffix in SECRET_SUFFIXES or name in SECRET_FILE_NAMES:
        return Finding(normalised, "secret key/certificate file must not be submitted")
    if suffix == ".log":
        return Finding(normalised, "generated log file must not be submitted")
    if suffix == ".json" and any(token in lowered for token in ("storage_state", "storage-state", "cookie", "session", "auth_state", "localstorage")):
        return Finding(normalised, "auth/session storage JSON must not be submitted")
    return None


def _check_text_content(root: Path, rel_path: str) -> list[Finding]:
    path = root / rel_path
    if not path.exists() or not _is_text_file(path):
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [Finding(rel_path, "could not inspect text content")]

    findings: list[Finding] = []
    for index, line in enumerate(lines, start=1):
        for reason, pattern in TOKEN_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(rel_path, f"{reason} detected at line {index}"))
                break

        if rel_path == ".env.example" or path.suffix.lower() == ".py":
            continue

        match = ENV_ASSIGNMENT_RE.match(line) or MAPPING_ASSIGNMENT_RE.match(line)
        if not match:
            continue
        key, value = match.groups()
        if _is_sensitive_key(key) and not _is_placeholder(value):
            findings.append(Finding(rel_path, f"possible non-placeholder secret assignment at line {index}"))
    return findings


def run_checks(root: Path, tracked_files: list[str] | None = None) -> list[Finding]:
    root = root.resolve()
    findings = _check_gitignore(root)
    findings.extend(_check_env_example(root))

    for rel_path in _candidate_files(root, tracked_files):
        forbidden = _check_forbidden_path(rel_path)
        if forbidden:
            findings.append(forbidden)
            continue
        findings.extend(_check_text_content(root, rel_path))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail when submission-unsafe files or obvious secrets are present.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    findings = run_checks(args.root)
    if findings:
        for finding in findings:
            print(f"FAIL {finding.path}: {finding.reason}")
        return 1

    print("Submission safety check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
