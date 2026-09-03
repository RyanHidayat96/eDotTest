from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class MobileDevice:
    serial: str
    status: str

    @property
    def is_ready(self) -> bool:
        return self.status == "device"


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
