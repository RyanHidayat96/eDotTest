from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from edot_qa.config import ROOT_DIR
from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.device import command_available
from edot_qa.reporting.allure_helpers import attach_file, attach_json, attach_text


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

    def build_command(self, flow: str | Path) -> list[str]:
        flow_path = self.resolve_flow(flow)
        command = [self.settings.maestro_cli]
        if self.settings.mobile_device_id:
            command.extend(["--device", self.settings.mobile_device_id])
        command.extend(["test", str(flow_path)])
        return command

    def resolve_flow(self, flow: str | Path) -> Path:
        flow_path = Path(flow)
        if flow_path.is_absolute():
            return flow_path
        if len(flow_path.parts) == 1:
            return self.settings.maestro_flow_dir / flow_path
        return ROOT_DIR / flow_path

    def run_flow(self, flow: str | Path, *, timeout_seconds: int = 300) -> MaestroResult:
        if not command_available(self.settings.maestro_cli):
            raise RuntimeError(f"Maestro CLI not found: {self.settings.maestro_cli}")

        flow_path = self.resolve_flow(flow)
        if not flow_path.is_file():
            raise FileNotFoundError(f"Maestro flow not found: {flow_path}")

        self.settings.ensure_runtime_dirs()
        command = self.build_command(flow_path)
        attach_json("maestro-command", {"command": command, "flow": str(flow_path)})

        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            env=self.settings.maestro_environment(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        result = MaestroResult(
            flow_path=flow_path,
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
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
