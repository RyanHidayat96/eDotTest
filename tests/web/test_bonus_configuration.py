from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_parallel_execution_bonus_is_configured() -> None:
    package = json.loads((ROOT_DIR / "package.json").read_text(encoding="utf-8"))
    parallel_script = package["scripts"]["test:parallel"]

    assert "-n auto" in parallel_script
    assert "not requires_credentials" in parallel_script
    assert "not requires_device" in parallel_script
    assert "not requires_maestro" in parallel_script
    assert "not requires_mobile_app" in parallel_script
    assert "not requires_storage_state" in parallel_script
    assert "not requires_cleanup" in parallel_script
    assert "not deliberate_failure" in parallel_script


def test_pytest_xdist_dependency_is_declared() -> None:
    project = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]

    assert any(dependency.startswith("pytest-xdist") for dependency in dependencies)


def test_web_to_mobile_handoff_bonus_script_is_configured() -> None:
    package = json.loads((ROOT_DIR / "package.json").read_text(encoding="utf-8"))
    handoff_script = package["scripts"]["test:e2e:handoff"]

    assert "tests/web/test_web_mobile_handoff.py::test_web_created_company_handoff_drives_mobile_login" in handoff_script
    assert "-q -rs" in handoff_script
