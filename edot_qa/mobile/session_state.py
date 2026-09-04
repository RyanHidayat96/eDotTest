from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_mobile_session_state(
    path: Path,
    *,
    app_id: str | None,
    device_id: str | None,
    dashboard_text: str | None,
) -> dict[str, Any]:
    payload = {
        "app_id": app_id or "<missing>",
        "device_id": device_id or "<auto>",
        "dashboard_text": dashboard_text or "<missing>",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "mobile-app-session-marker",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def mobile_session_state_exists(path: Path, *, app_id: str | None = None) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload.get("kind") != "mobile-app-session-marker":
        return False
    if app_id and payload.get("app_id") != app_id:
        return False
    return True
