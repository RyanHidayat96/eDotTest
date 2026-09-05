from __future__ import annotations

import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_web_to_mobile_handoff_bonus_script_is_configured() -> None:
    package = json.loads((ROOT_DIR / "package.json").read_text(encoding="utf-8"))
    handoff_script = package["scripts"]["test:handoff"]

    assert "tests/web/test_web_mobile_handoff.py::test_web_created_company_handoff_drives_mobile_login" in handoff_script
    assert "-q -rs" in handoff_script
