from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from edot_qa.config import ROOT_DIR
from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.device import capture_device_screenshot, command_available
from edot_qa.reporting.allure_helpers import (
    allure_step,
    attach_file,
    attach_json,
    attach_png,
    attach_text,
    show_dev_inputs_in_reports,
)


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
        with allure_step(
            f"Run Maestro flow: {flow_path.name}",
            data={
                "flow": str(flow_path),
                "timeout_seconds": timeout_seconds,
                "device_id": self.settings.mobile_device_id or "<auto>",
                "extra_env_keys": sorted((extra_env or {}).keys()),
            },
            screenshot=False,
        ):
            flow_inputs = maestro_flow_inputs(
                flow_path.name,
                maestro_variables,
                reveal_login_secrets=show_dev_inputs_in_reports(),
            )
            if flow_inputs:
                attach_json("Inputs", flow_inputs, redact=False)
            attach_json("maestro-command", {"command": redacted_command, "flow": str(flow_path)})
            attach_file("maestro-flow-yaml", flow_path)

            try:
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
            except subprocess.TimeoutExpired as error:
                result = MaestroResult(
                    flow_path=flow_path,
                    command=redacted_command,
                    returncode=124,
                    stdout=redact_sensitive_text(_timeout_output(error.stdout), maestro_variables),
                    stderr=f"Maestro flow timed out after {timeout_seconds}s: {flow_path.name}",
                )
            self.attach_result(result)
            self.attach_device_screenshot()
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

    def attach_device_screenshot(self) -> None:
        image = capture_device_screenshot(
            self.settings.adb_command,
            device_id=self.settings.mobile_device_id,
            timeout_seconds=5,
        )
        if image:
            attach_png("maestro-device-screenshot", image)


def assert_maestro_passed(result: MaestroResult) -> MaestroResult:
    if result.passed:
        return result
    raise AssertionError(
        f"Maestro flow failed with exit code {result.returncode}: {result.flow_path.name}\n{result.stderr}".strip()
    )


def maestro_flow_inputs(
    flow_name: str,
    variables: dict[str, str],
    *,
    reveal_login_secrets: bool = True,
) -> dict[str, object]:
    if flow_name == "login.yaml":
        return {
            "fields": {
                "Company ID": _login_input_value("EWORK_COMPANY_CODE", variables, reveal_login_secrets),
                "Username": _login_input_value("EWORK_EMAIL", variables, reveal_login_secrets),
                "Password": _login_input_value("EWORK_PASSWORD", variables, reveal_login_secrets),
            }
        }

    if flow_name == "create_customer_basic.yaml":
        return {"fields": _customer_basic_inputs(variables)}

    if flow_name == "create_customer_locations.yaml":
        return {"fields": _customer_location_inputs(variables)}

    if flow_name == "create_customer_documents.yaml":
        return {"fields": _customer_document_inputs(variables)}

    if flow_name == "validate_customer_list_card.yaml":
        return {
            "expected_card": {
                "Name": variables.get("EWORK_CUSTOMER_NAME", ""),
                "Address": variables.get("EWORK_CUSTOMER_CARD_ADDRESS", ""),
                "Customer Type": variables.get("EWORK_CUSTOMER_TYPE_OPTION_TEXT", ""),
            }
        }

    return {}


def _login_input_value(key: str, variables: dict[str, str], reveal_login_secrets: bool) -> str:
    if not reveal_login_secrets and variables.get(key):
        return "<redacted>"
    return variables.get(key, "")


def _customer_basic_inputs(variables: dict[str, str]) -> dict[str, str]:
    return {
        "Outlet Name": variables.get("EWORK_CUSTOMER_NAME", ""),
        "Contact": variables.get("EWORK_CUSTOMER_CONTACT", ""),
        "Contact Person": variables.get("EWORK_CUSTOMER_CONTACT_PERSON", ""),
        "Channel": variables.get("EWORK_CUSTOMER_CHANNEL_OPTION_TEXT", ""),
        "Customer Type": variables.get("EWORK_CUSTOMER_TYPE_OPTION_TEXT", ""),
    }


def _customer_location_inputs(variables: dict[str, str]) -> dict[str, str]:
    return {
        "Address Type": variables.get("EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT", ""),
        "Current Location": "Use my current location",
        "Province": variables.get("EWORK_CUSTOMER_PROVINCE_OPTION_TEXT", ""),
        "City": variables.get("EWORK_CUSTOMER_CITY_OPTION_TEXT", ""),
        "District": variables.get("EWORK_CUSTOMER_DISTRICT_OPTION_TEXT", ""),
        "Sub District": variables.get("EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT", ""),
        "Postal Code": variables.get("EWORK_CUSTOMER_POSTAL_CODE_OPTION_TEXT", ""),
    }


def _customer_document_inputs(variables: dict[str, str]) -> dict[str, str]:
    return {
        "KTP": variables.get("EWORK_CUSTOMER_KTP_NUMBER", ""),
        "Attachment": "camera capture",
        "Signature": "drawn",
    }


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


def _timeout_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
