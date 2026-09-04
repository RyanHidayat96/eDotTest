from __future__ import annotations

import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class MobileDevice:
    serial: str
    status: str

    @property
    def is_ready(self) -> bool:
        return self.status == "device"


@dataclass(frozen=True)
class ScrollSearchResult:
    reached_end: bool
    down_swipes: int
    up_swipes: int
    visible_texts: list[str]


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def adb_devices(adb_command: str = "adb", *, timeout_seconds: int = 10) -> list[MobileDevice]:
    try:
        completed = _run_adb([adb_command, "devices"], timeout_seconds=timeout_seconds)
    except FileNotFoundError as error:
        raise RuntimeError(f"ADB command not found: {adb_command}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"ADB devices command timed out after {timeout_seconds}s") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ADB devices command failed: {error.stderr}") from error
    return parse_adb_devices(completed.stdout)


def package_installed(
    package_name: str,
    adb_command: str = "adb",
    *,
    device_id: str | None = None,
    timeout_seconds: int = 10,
) -> bool:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    command.extend(["shell", "pm", "list", "packages", package_name])
    try:
        completed = _run_adb(command, timeout_seconds=timeout_seconds)
    except RuntimeError:
        return False

    expected = f"package:{package_name}"
    return any(line.strip() == expected for line in completed.stdout.splitlines())


def clear_app_data(
    package_name: str,
    adb_command: str = "adb",
    *,
    device_id: str | None = None,
    timeout_seconds: int = 10,
) -> str:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    command.extend(["shell", "pm", "clear", package_name])
    completed = _run_adb(command, timeout_seconds=timeout_seconds)
    return completed.stdout.strip()


def force_stop_app(
    package_name: str,
    adb_command: str = "adb",
    *,
    device_id: str | None = None,
    timeout_seconds: int = 10,
) -> str:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    command.extend(["shell", "am", "force-stop", package_name])
    completed = _run_adb(command, timeout_seconds=timeout_seconds)
    return completed.stdout.strip()


def wake_device(
    adb_command: str = "adb",
    *,
    device_id: str | None = None,
    timeout_seconds: int = 10,
) -> str:
    base_command = [adb_command]
    if device_id:
        base_command.extend(["-s", device_id])

    outputs = []
    for shell_command in (
        ["shell", "input", "keyevent", "KEYCODE_WAKEUP"],
        ["shell", "wm", "dismiss-keyguard"],
    ):
        completed = _run_adb([*base_command, *shell_command], timeout_seconds=timeout_seconds)
        if completed.stdout.strip():
            outputs.append(completed.stdout.strip())
    return "\n".join(outputs)


def scroll_list_to_end_and_find_texts(
    required_texts: list[str],
    adb_command: str = "adb",
    *,
    device_id: str | None = None,
    bottom_timeout_seconds: int = 30,
    search_timeout_seconds: int = 30,
    max_down_swipes: int = 300,
    max_up_swipes: int = 4,
    down_swipe_batch_size: int = 20,
) -> ScrollSearchResult:
    width, height = _screen_size(adb_command, device_id=device_id, timeout_seconds=10)
    visible_texts = _visible_text_signature(adb_command, device_id=device_id, timeout_seconds=10)
    if _all_required_texts_visible(required_texts, visible_texts):
        return ScrollSearchResult(
            reached_end=False,
            down_swipes=0,
            up_swipes=0,
            visible_texts=visible_texts,
        )

    previous_signature = tuple(visible_texts)
    down_swipes = 0
    unchanged_count = 0
    bottom_deadline = time.monotonic() + bottom_timeout_seconds

    while time.monotonic() < bottom_deadline and down_swipes < max_down_swipes:
        batch_size = min(down_swipe_batch_size, max_down_swipes - down_swipes)
        _adb_swipe_batch(
            adb_command,
            device_id=device_id,
            width=width,
            height=height,
            start_y_ratio=0.88,
            end_y_ratio=0.3,
            duration_ms=10,
            count=batch_size,
            timeout_seconds=15,
        )
        down_swipes += batch_size
        time.sleep(0.15)
        visible_texts = _visible_text_signature(adb_command, device_id=device_id, timeout_seconds=10)
        if _all_required_texts_visible(required_texts, visible_texts):
            return ScrollSearchResult(
                reached_end=False,
                down_swipes=down_swipes,
                up_swipes=0,
                visible_texts=visible_texts,
            )

        current_signature = tuple(visible_texts)
        if current_signature == previous_signature:
            unchanged_count += 1
            if unchanged_count >= 2:
                break
        else:
            unchanged_count = 0
            previous_signature = current_signature

    reached_end = unchanged_count >= 2
    if _all_required_texts_visible(required_texts, visible_texts):
        return ScrollSearchResult(
            reached_end=reached_end,
            down_swipes=down_swipes,
            up_swipes=0,
            visible_texts=visible_texts,
        )

    up_swipes = 0
    search_deadline = time.monotonic() + search_timeout_seconds
    while time.monotonic() < search_deadline and up_swipes < max_up_swipes:
        _adb_swipe(
            adb_command,
            device_id=device_id,
            width=width,
            height=height,
            start_y_ratio=0.45,
            end_y_ratio=0.75,
            duration_ms=700,
            timeout_seconds=10,
        )
        up_swipes += 1
        time.sleep(0.35)
        visible_texts = _visible_text_signature(adb_command, device_id=device_id, timeout_seconds=10)
        if _all_required_texts_visible(required_texts, visible_texts):
            return ScrollSearchResult(
                reached_end=reached_end,
                down_swipes=down_swipes,
                up_swipes=up_swipes,
                visible_texts=visible_texts,
            )

    missing = _missing_required_texts(required_texts, visible_texts)
    raise AssertionError(f"Created customer card not visible from list bottom. Missing: {', '.join(missing)}")


def visible_texts_by_resource_id(
    resource_ids: list[str],
    adb_command: str = "adb",
    *,
    device_id: str | None = None,
    timeout_seconds: int = 10,
) -> dict[str, list[str]]:
    xml_text = _dump_window_xml(adb_command, device_id=device_id, timeout_seconds=timeout_seconds)
    return _visible_texts_by_resource_id_from_xml(xml_text, resource_ids)


def capture_device_screenshot(
    adb_command: str = "adb",
    *,
    device_id: str | None = None,
    timeout_seconds: int = 10,
) -> bytes | None:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    command.extend(["exec-out", "screencap", "-p"])
    try:
        completed = subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return None
    return completed.stdout or None


def parse_adb_devices(output: str) -> list[MobileDevice]:
    devices: list[MobileDevice] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        columns = line.split()
        if len(columns) >= 2:
            devices.append(MobileDevice(serial=columns[0], status=columns[1]))
    return devices


def ready_device(devices: list[MobileDevice], requested_serial: str | None = None) -> MobileDevice | None:
    for device in devices:
        if not device.is_ready:
            continue
        if requested_serial is None or device.serial == requested_serial:
            return device
    return None


def _run_adb(command: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"ADB command not found: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"ADB command timed out after {timeout_seconds}s: {' '.join(command)}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ADB command failed: {error.stderr}") from error


def _screen_size(
    adb_command: str,
    *,
    device_id: str | None,
    timeout_seconds: int,
) -> tuple[int, int]:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    command.extend(["shell", "wm", "size"])
    completed = _run_adb(command, timeout_seconds=timeout_seconds)
    for line in completed.stdout.splitlines():
        if "size:" not in line:
            continue
        raw_size = line.split("size:", 1)[1].strip()
        width, height = raw_size.split("x", 1)
        return int(width), int(height)
    raise RuntimeError(f"Unable to read Android screen size: {completed.stdout}")


def _adb_swipe(
    adb_command: str,
    *,
    device_id: str | None,
    width: int,
    height: int,
    start_y_ratio: float,
    end_y_ratio: float,
    duration_ms: int,
    timeout_seconds: int,
) -> None:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    x = width // 2
    start_y = int(height * start_y_ratio)
    end_y = int(height * end_y_ratio)
    command.extend(["shell", "input", "swipe", str(x), str(start_y), str(x), str(end_y), str(duration_ms)])
    _run_adb(command, timeout_seconds=timeout_seconds)


def _adb_swipe_batch(
    adb_command: str,
    *,
    device_id: str | None,
    width: int,
    height: int,
    start_y_ratio: float,
    end_y_ratio: float,
    duration_ms: int,
    count: int,
    timeout_seconds: int,
) -> None:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    x = width // 2
    start_y = int(height * start_y_ratio)
    end_y = int(height * end_y_ratio)
    shell_script = (
        f"i=0; while [ $i -lt {count} ]; do "
        f"input swipe {x} {start_y} {x} {end_y} {duration_ms}; "
        "i=$((i+1)); done"
    )
    command.extend(["shell", shell_script])
    _run_adb(command, timeout_seconds=timeout_seconds)


def _visible_text_signature(
    adb_command: str,
    *,
    device_id: str | None,
    timeout_seconds: int,
) -> list[str]:
    xml_text = _dump_window_xml(adb_command, device_id=device_id, timeout_seconds=timeout_seconds)
    root = ET.fromstring(xml_text)
    texts: list[str] = []
    for node in root.iter("node"):
        for attribute in ("text", "content-desc"):
            value = (node.attrib.get(attribute) or "").strip()
            if value:
                texts.append(value)
    return texts


def _visible_texts_by_resource_id_from_xml(xml_text: str, resource_ids: list[str]) -> dict[str, list[str]]:
    wanted = set(resource_ids)
    texts_by_id: dict[str, list[str]] = {resource_id: [] for resource_id in resource_ids}
    root = ET.fromstring(xml_text)
    for node in root.iter("node"):
        resource_id = node.attrib.get("resource-id")
        if resource_id not in wanted:
            continue
        value = _normalize_text(node.attrib.get("text") or node.attrib.get("content-desc") or "")
        if value:
            texts_by_id[resource_id].append(value)
    return texts_by_id


def _dump_window_xml(
    adb_command: str,
    *,
    device_id: str | None,
    timeout_seconds: int,
) -> str:
    command = [adb_command]
    if device_id:
        command.extend(["-s", device_id])
    try:
        _run_adb(
            [*command, "shell", "uiautomator", "dump", "--compressed", "/sdcard/edot-window.xml"],
            timeout_seconds=timeout_seconds,
        )
    except RuntimeError:
        _run_adb([*command, "shell", "uiautomator", "dump", "/sdcard/edot-window.xml"], timeout_seconds=timeout_seconds)
    completed = _run_adb([*command, "exec-out", "cat", "/sdcard/edot-window.xml"], timeout_seconds=timeout_seconds)
    return completed.stdout


def _all_required_texts_visible(required_texts: list[str], visible_texts: list[str]) -> bool:
    return not _missing_required_texts(required_texts, visible_texts)


def _missing_required_texts(required_texts: list[str], visible_texts: list[str]) -> list[str]:
    missing = []
    normalized_visible_texts = [_normalize_text(visible_text) for visible_text in visible_texts]
    for required_text in required_texts:
        normalized_required_text = _normalize_text(required_text)
        if normalized_required_text and not any(
            normalized_required_text in visible_text for visible_text in normalized_visible_texts
        ):
            missing.append(required_text)
    return missing


def _normalize_text(value: str) -> str:
    return " ".join(value.split())
