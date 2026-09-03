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
        completed = subprocess.run(
            [adb_command, "devices"],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"ADB command not found: {adb_command}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"ADB devices command timed out after {timeout_seconds}s") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ADB devices command failed: {error.stderr}") from error
    return parse_adb_devices(completed.stdout)


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
