from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator


try:
    import allure
except ModuleNotFoundError:
    allure = None


SENSITIVE_KEY = ("authorization", "cookie", "password", "passwd", "token", "secret", "credential", "session")
MAX_ARRAY_ITEMS = 25


def attach_text(name: str, text: str) -> None:
    if allure is None:
        return
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_json(name: str, payload: Any) -> None:
    if allure is None:
        return
    allure.attach(
        json.dumps(redact_payload(payload), indent=2, sort_keys=True),
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
    screenshot: bool = True,
    full_page: bool = False,
) -> Iterator[None]:
    if allure is None:
        yield
        return

    started_at = perf_counter()
    with allure.step(title):
        if data is not None:
            attach_json("step-input", data)
        try:
            yield
        except Exception as error:
            attach_json(
                "step-error",
                {"error_type": type(error).__name__, "message": str(error)},
            )
            if page is not None:
                attach_page_evidence("step-failure-evidence", page, screenshot=screenshot, full_page=full_page)
            raise
        else:
            attach_json("step-result", {"status": "passed", "duration_ms": int((perf_counter() - started_at) * 1000)})
            if page is not None:
                attach_page_evidence("step-evidence", page, screenshot=screenshot, full_page=full_page)


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
        f"{name}-page",
        {
            "url": _page_url(page),
            "title": _page_title(page),
            "viewport": _page_viewport(page),
        },
    )
    if not screenshot:
        return
    try:
        attach_png(f"{name}-screenshot", page.screenshot(full_page=full_page, timeout=5_000))
    except Exception as error:
        attach_text(f"{name}-screenshot-error", str(error))


def redact_payload(value: Any) -> Any:
    return _normalize_payload(value)


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
