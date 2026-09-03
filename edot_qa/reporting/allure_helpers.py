from __future__ import annotations

import json
from pathlib import Path
from typing import Any


try:
    import allure
except ModuleNotFoundError:
    allure = None


def attach_text(name: str, text: str) -> None:
    if allure is None:
        return
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_json(name: str, payload: Any) -> None:
    if allure is None:
        return
    allure.attach(
        json.dumps(payload, indent=2, sort_keys=True),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def attach_png(name: str, image_bytes: bytes) -> None:
    if allure is None:
        return
    allure.attach(image_bytes, name=name, attachment_type=allure.attachment_type.PNG)


def attach_file(name: str, path: str | Path, attachment_type: Any | None = None) -> None:
    if allure is None:
        return
    resolved_path = Path(path)
    if not resolved_path.is_file():
        return
    allure.attach.file(str(resolved_path), name=name, attachment_type=attachment_type)
