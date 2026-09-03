from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from edot_qa.config import ROOT_DIR
from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.device import command_available
from edot_qa.reporting.allure_helpers import attach_file, attach_json, attach_text


SENSITIVE_MAESTRO_KEYS = {"EWORK_EMAIL", "EWORK_PASSWORD", "EWORK_COMPANY_CODE"}


@dataclass(frozen=True)
class MaestroResult:
    flow_path: Path
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


class MaestroRunner:
    def __init__(self, settings: MobileSettings) -> None:
        self.settings = settings

    def build_command(
        self,
        flow: str | Path,
        *,
        include_env_flags: bool = False,
        extra_env: dict[str, str] | None = None,
    ) -> list[str]:
        flow_path = self.resolve_flow(flow)
        command = [self.settings.maestro_cli]
        if self.settings.mobile_device_id:
            command.extend(["--device", self.settings.mobile_device_id])
        command.append("test")
        if include_env_flags:
            for key, value in self.settings.maestro_variables(extra_env).items():
                command.extend(["-e", f"{key}={value}"])
        command.append(str(flow_path))
        return command

    def resolve_flow(self, flow: str | Path) -> Path:
        flow_path = Path(flow)
        if flow_path.is_absolute():
            return flow_path
        if len(flow_path.parts) == 1:
            return self.settings.maestro_flow_dir / flow_path
        flow_dir_path = self.settings.maestro_flow_dir / flow_path
        if flow_dir_path.is_file():
            return flow_dir_path
        return ROOT_DIR / flow_path

    def run_flow(
        self,
        flow: str | Path,
        *,
        timeout_seconds: int = 60,
        extra_env: dict[str, str] | None = None,
    ) -> MaestroResult:
        if not command_available(self.settings.maestro_cli):
            raise RuntimeError(f"Maestro CLI not found: {self.settings.maestro_cli}")

        flow_path = self.resolve_flow(flow)
        if not flow_path.is_file():
            raise FileNotFoundError(f"Maestro flow not found: {flow_path}")

        self.settings.ensure_runtime_dirs()
        maestro_variables = self.settings.maestro_variables(extra_env)
        command = self.build_command(flow_path, include_env_flags=True, extra_env=extra_env)
        redacted_command = redact_command(command, maestro_variables)
        attach_json("maestro-command", {"command": redacted_command, "flow": str(flow_path)})

        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            env=self.settings.maestro_environment(extra_env),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        result = MaestroResult(
            flow_path=flow_path,
            command=redacted_command,
            returncode=completed.returncode,
            stdout=redact_sensitive_text(completed.stdout, maestro_variables),
            stderr=redact_sensitive_text(completed.stderr, maestro_variables),
        )
        self.attach_result(result)
        return result

    def attach_result(self, result: MaestroResult) -> None:
        attach_text("maestro-stdout", result.stdout)
        attach_text("maestro-stderr", result.stderr)
        attach_json(
            "maestro-result",
            {
                "flow": str(result.flow_path),
                "returncode": result.returncode,
                "passed": result.passed,
            },
        )
        self.attach_output_artifacts()

    def attach_output_artifacts(self) -> None:
        if not self.settings.maestro_output_dir.is_dir():
            return
        for path in sorted(self.settings.maestro_output_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".log", ".mp4", ".png", ".txt", ".webm"}:
                attach_file(f"maestro-artifact-{path.name}", path)


def assert_maestro_passed(result: MaestroResult) -> MaestroResult:
    if result.passed:
        return result
    raise AssertionError(
        f"Maestro flow failed with exit code {result.returncode}: {result.flow_path.name}\n{result.stderr}".strip()
    )


def redact_command(command: list[str], variables: dict[str, str] | None = None) -> list[str]:
    return [redact_sensitive_text(value, variables) for value in command]


def redact_sensitive_text(text: str, variables: dict[str, str] | None = None) -> str:
    redacted = text
    for key in SENSITIVE_MAESTRO_KEYS:
        value = (variables or {}).get(key)
        if value:
            redacted = redacted.replace(f"{key}={value}", f"{key}=<redacted>")
            redacted = redacted.replace(value, "<redacted>")
    return redacted
