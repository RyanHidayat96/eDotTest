from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterator


try:
    import allure
except ModuleNotFoundError:
    allure = None


SENSITIVE_KEY = ("authorization", "cookie", "password", "passwd", "token", "secret", "credential", "session")
MAX_ARRAY_ITEMS = 25
_STEP_DEPTH: ContextVar[int] = ContextVar("_STEP_DEPTH", default=0)
_STEP_INPUTS: ContextVar[list[dict[str, Any]] | None] = ContextVar("_STEP_INPUTS", default=None)
TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def attach_text(name: str, text: str) -> None:
    if allure is None:
        return
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_json(name: str, payload: Any, *, redact: bool = True) -> None:
    if allure is None:
        return
    allure.attach(
        json.dumps(redact_payload(payload) if redact else payload, indent=2, sort_keys=True),
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


@contextmanager
def allure_step(
    title: str,
    *,
    page: Any | None = None,
    data: Any | None = None,
    input_data: Any | None = None,
    screenshot: bool = False,
    full_page: bool = False,
    force: bool = False,
) -> Iterator[None]:
    if allure is None:
        yield
        return

    depth = _STEP_DEPTH.get()
    if depth > 0 and not force and not screenshot:
        if input_data is not None:
            _record_input(title, input_data)
        try:
            yield
        except Exception as error:
            attach_json(
                f"Error - {title}",
                {"error_type": type(error).__name__, "message": str(error)},
            )
            if page is not None:
                attach_page_evidence(f"Failure - {title}", page, screenshot=True, full_page=True)
            raise
        return

    with allure.step(title):
        token = _STEP_DEPTH.set(depth + 1)
        input_token = _STEP_INPUTS.set([])
        if input_data is not None:
            _record_input(title, input_data)
        try:
            yield
        except Exception as error:
            _attach_collected_inputs()
            attach_json(
                "Error",
                {"error_type": type(error).__name__, "message": str(error)},
            )
            if page is not None:
                attach_page_evidence("Failure", page, screenshot=True, full_page=True)
            raise
        else:
            _attach_collected_inputs()
            if page is not None and screenshot:
                attach_page_evidence("Evidence", page, screenshot=True, full_page=full_page)
        finally:
            _STEP_INPUTS.reset(input_token)
            _STEP_DEPTH.reset(token)


def attach_page_evidence(
    name: str,
    page: Any,
    *,
    screenshot: bool = True,
    full_page: bool = False,
) -> None:
    if allure is None or _page_is_closed(page):
        return

    attach_json(
        f"{name} page state",
        {
            "url": _page_url(page),
            "title": _page_title(page),
            "viewport": _page_viewport(page),
        },
    )
    if not screenshot:
        return
    try:
        attach_png(f"{name} screenshot", page.screenshot(full_page=full_page, timeout=5_000))
    except Exception as error:
        attach_text(f"{name} screenshot error", str(error))


def redact_payload(value: Any) -> Any:
    return _normalize_payload(value)


def show_dev_inputs_in_reports() -> bool:
    return os.getenv("ALLURE_SHOW_DEV_INPUTS", "true").strip().lower() in TRUE_VALUES


def _record_input(title: str, data: Any) -> None:
    inputs = _STEP_INPUTS.get()
    if inputs is None:
        attach_json("Inputs", data)
        return
    inputs.append({"step": title, "data": redact_payload(data)})


def _attach_collected_inputs() -> None:
    inputs = _STEP_INPUTS.get()
    if not inputs:
        return
    attach_json("Inputs", _combined_inputs(inputs))


def _combined_inputs(inputs: list[dict[str, Any]]) -> Any:
    fields: dict[str, Any] = {}
    records = []
    for item in inputs:
        data = item.get("data")
        if isinstance(data, dict) and {"field", "value"}.issubset(data):
            fields[str(data["field"])] = data["value"]
            continue
        records.append({"step": item.get("step"), "data": data})
    if fields:
        return {"fields": fields}
    if len(records) == 1:
        return records[0]["data"]
    return {"items": records}


def _normalize_payload(value: Any, *, key: str = "") -> Any:
    if _is_sensitive_key(key):
        return "<redacted>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _normalize_payload(asdict(value), key=key)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _normalize_payload(value.model_dump(), key=key)
    if isinstance(value, dict):
        return {str(child_key): _normalize_payload(child_value, key=str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        head = [_normalize_payload(item, key=key) for item in items[:MAX_ARRAY_ITEMS]]
        if len(items) > MAX_ARRAY_ITEMS:
            head.append({"__truncated": len(items) - MAX_ARRAY_ITEMS})
        return head
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in SENSITIVE_KEY)


def _page_is_closed(page: Any) -> bool:
    is_closed = getattr(page, "is_closed", None)
    if not callable(is_closed):
        return False
    try:
        return bool(is_closed())
    except Exception:
        return True


def _page_url(page: Any) -> str:
    try:
        return str(page.url)
    except Exception:
        return "<unavailable>"


def _page_title(page: Any) -> str:
    title = getattr(page, "title", None)
    if not callable(title):
        return "<unavailable>"
    try:
        return str(title())
    except Exception:
        return "<unavailable>"


def _page_viewport(page: Any) -> Any:
    try:
        return page.viewport_size
    except Exception:
        return "<unavailable>"
