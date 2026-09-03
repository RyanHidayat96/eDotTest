from __future__ import annotations

import ast
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_no_arbitrary_sleep_calls_in_automation_code():
    offenders = []
    for path in _python_files(ROOT_DIR / "edot_qa", ROOT_DIR / "tests"):
        for call in _calls(path):
            if isinstance(call.func, ast.Name) and call.func.id == "sleep":
                offenders.append(f"{path.relative_to(ROOT_DIR)}:{call.lineno}")
            if isinstance(call.func, ast.Attribute) and call.func.attr == "sleep":
                offenders.append(f"{path.relative_to(ROOT_DIR)}:{call.lineno}")

    assert offenders == []


def test_no_raw_playwright_selectors_in_web_tests():
    banned_attributes = {
        "loc" + "ator",
        "query" + "_selector",
        "query" + "_selector_all",
        "wait" + "_for_selector",
    }
    offenders = []
    for path in _python_files(ROOT_DIR / "tests" / "web"):
        for call in _calls(path):
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr in banned_attributes or call.func.attr.startswith("get" + "_by_"):
                offenders.append(f"{path.relative_to(ROOT_DIR)}:{call.lineno}:{call.func.attr}")

    assert offenders == []


def test_env_example_keeps_runtime_secrets_empty():
    env_values = {}
    for line in (ROOT_DIR / ".env.example").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_values[key] = value

    for key in ("ESUITE_EMAIL", "ESUITE_PASSWORD", "OPENAI_API_KEY"):
        assert env_values[key] == ""


def test_no_tracked_runtime_or_tool_artifacts():
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = completed.stdout.splitlines()
    banned_parts = (
        ".agents/",
        ".codex/",
        ".claude/",
        ".cursor/",
        ".continue/",
        ".egg-info/",
        ".pytest_cache/",
        "__pycache__/",
        "artifacts/",
        "playwright-report/",
        "reports/allure-report/",
        "reports/allure-results/",
        "test-results/",
    )
    banned_names = ("~$", ".tmp", ".temp", ".bak", ".orig", ".rej")

    offenders = [
        path
        for path in tracked
        if any(part in path for part in banned_parts) or any(name in Path(path).name for name in banned_names)
    ]

    assert offenders == []


def _python_files(*roots: Path) -> list[Path]:
    return [path for root in roots for path in sorted(root.rglob("*.py"))]


def _calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
