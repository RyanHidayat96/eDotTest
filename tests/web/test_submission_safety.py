from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "check_submission_safety.py"
SPEC = importlib.util.spec_from_file_location("check_submission_safety", MODULE_PATH)
assert SPEC and SPEC.loader
submission_safety = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = submission_safety
SPEC.loader.exec_module(submission_safety)


def write_baseline(root: Path) -> None:
    root.joinpath(".gitignore").write_text(
        "\n".join(
            [
                ".env",
                ".env.*",
                "!.env.example",
                "artifacts/",
                "reports/",
                "allure-results/",
                "allure-report/",
                "*.key",
                "*.pem",
            ]
        ),
        encoding="utf-8",
    )
    root.joinpath(".env.example").write_text(
        "\n".join(
            [
                "ESUITE_BASE_URL=https://esuite.edot.id",
                "ESUITE_PASSWORD=",
                "GEMINI_API_KEY=",
                "GEMINI_TEST_DATA_MODEL=gemini-3.1-flash-lite",
                "EWORK_PASSWORD_FIELD_ID=id.edot.ework:id/tv_password",
            ]
        ),
        encoding="utf-8",
    )


def test_checker_allows_blank_secret_template_values(tmp_path: Path) -> None:
    write_baseline(tmp_path)

    findings = submission_safety.run_checks(tmp_path, tracked_files=[".gitignore", ".env.example"])

    assert findings == []


def test_checker_flags_env_without_printing_value(tmp_path: Path) -> None:
    write_baseline(tmp_path)
    secret_value = "super-secret-value"
    tmp_path.joinpath(".env").write_text(f"GEMINI_API_KEY={secret_value}\n", encoding="utf-8")

    findings = submission_safety.run_checks(tmp_path, tracked_files=[".gitignore", ".env.example", ".env"])
    rendered = "\n".join(f"{finding.path}: {finding.reason}" for finding in findings)

    assert ".env" in rendered
    assert secret_value not in rendered


def test_checker_flags_non_placeholder_secret_assignments(tmp_path: Path) -> None:
    write_baseline(tmp_path)
    secret_value = "live-production-key"
    tmp_path.joinpath("README.md").write_text(f"GEMINI_API_KEY={secret_value}\n", encoding="utf-8")

    findings = submission_safety.run_checks(tmp_path, tracked_files=[".gitignore", ".env.example", "README.md"])
    rendered = "\n".join(f"{finding.path}: {finding.reason}" for finding in findings)

    assert "README.md" in rendered
    assert secret_value not in rendered


def test_checker_flags_auth_storage_json(tmp_path: Path) -> None:
    write_baseline(tmp_path)
    auth_path = tmp_path / "artifacts" / "auth" / "esuite_storage_state.json"
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text("{}", encoding="utf-8")

    findings = submission_safety.run_checks(
        tmp_path,
        tracked_files=[".gitignore", ".env.example", "artifacts/auth/esuite_storage_state.json"],
    )

    assert any("auth/session" in finding.reason or "runtime artifact" in finding.reason for finding in findings)
