from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from edot_qa.config import ROOT_DIR
from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.device import capture_device_screenshot, command_available
from edot_qa.reporting.allure_helpers import (
    allure_step,
    attach_json,
    attach_png,
    show_dev_inputs_in_reports,
)

try:
    import allure
except ModuleNotFoundError:  # pragma: no cover - depends on optional reporting package.
    allure = None


SENSITIVE_MAESTRO_KEYS = {"EWORK_EMAIL", "EWORK_PASSWORD", "EWORK_COMPANY_CODE"}
MAX_FAILURE_OUTPUT_CHARS = 4_000


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
        step_title: str | None = None,
        expected: str | None = None,
    ) -> MaestroResult:
        if not command_available(self.settings.maestro_cli):
            raise RuntimeError(f"Maestro CLI not found: {self.settings.maestro_cli}")

        flow_path = self.resolve_flow(flow)
        if not flow_path.is_file():
            raise FileNotFoundError(f"Maestro flow not found: {flow_path}")

        self.settings.ensure_runtime_dirs()
        screenshot_dir = self._prepare_screenshot_dir(flow_path)
        maestro_variables = self.settings.maestro_variables(extra_env)
        command = self.build_command(flow_path, include_env_flags=True, extra_env=extra_env)
        redacted_command = redact_command(command, maestro_variables)
        with allure_step(
            business_step_title(flow_path.name, step_title=step_title, expected=expected),
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
            self.attach_result(result, screenshot_dir=screenshot_dir, flow_inputs=flow_inputs)
            return result

    def attach_result(
        self,
        result: MaestroResult,
        *,
        screenshot_dir: Path,
        flow_inputs: dict[str, object] | None = None,
    ) -> None:
        screenshots_attached = self.attach_flow_screenshots(screenshot_dir, flow_inputs=flow_inputs)

        if result.passed:
            if not screenshots_attached:
                if flow_inputs:
                    attach_json("Inputs", flow_inputs, redact=False)
                self.attach_device_screenshot("Screenshot")
            return

        if not screenshots_attached:
            if flow_inputs:
                attach_json("Inputs", flow_inputs, redact=False)
            self.attach_device_screenshot("Failure screenshot")
        attach_json(
            "Failure diagnostics",
            {
                "flow": str(result.flow_path),
                "returncode": result.returncode,
                "command": result.command,
                "stdout_tail": _tail(result.stdout),
                "stderr_tail": _tail(result.stderr),
            },
            redact=False,
        )

    def attach_flow_screenshots(self, screenshot_dir: Path, *, flow_inputs: dict[str, object] | None = None) -> int:
        screenshots = sorted(screenshot_dir.glob("*.png"))
        for screenshot in screenshots:
            try:
                image = screenshot.read_bytes()
            except OSError:
                continue
            step_title = _screenshot_step_title(screenshot)
            step_inputs = _inputs_for_screenshot(screenshot, flow_inputs)
            attachment_name = _evidence_payload_name(step_inputs)
            if allure is None:
                if step_inputs:
                    attach_json(f"{attachment_name} - {step_title}", step_inputs, redact=False)
                attach_png(f"Screenshot - {step_title}", image)
                continue
            with allure.step(step_title):
                if step_inputs:
                    attach_json(attachment_name, step_inputs, redact=False)
                attach_png("Screenshot", image)
        return len(screenshots)

    def attach_device_screenshot(self, name: str) -> None:
        image = capture_device_screenshot(
            self.settings.adb_command,
            device_id=self.settings.mobile_device_id,
            timeout_seconds=5,
        )
        if image:
            attach_png(name, image)

    @staticmethod
    def _prepare_screenshot_dir(flow_path: Path) -> Path:
        screenshot_dir = ROOT_DIR / "reports" / "maestro-screenshots" / flow_path.stem
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        for screenshot in screenshot_dir.glob("*.png"):
            try:
                screenshot.unlink()
            except OSError:
                continue
        return screenshot_dir


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


def business_step_title(flow_name: str, *, step_title: str | None = None, expected: str | None = None) -> str:
    title = step_title or FLOW_STEP_TITLES.get(flow_name) or f"Run Maestro flow: {flow_name}"
    if expected:
        return f"{title}. Expected: {expected}"
    return title


FLOW_STEP_TITLES = {
    "login.yaml": "Login to eWork",
    "create_customer_basic.yaml": "Complete Basic customer page",
    "create_customer_locations.yaml": "Complete Location page",
    "create_customer_documents.yaml": "Complete Documents page",
    "validate_customer_list_card.yaml": "Verify created customer card",
}

SCREENSHOT_STEP_TITLES = {
    "open-ework-app-expected-login-page-is-displayed": "Open eWork app. Expected: Login page is displayed",
    "enter-ework-login-credentials-expected-company-id-username-and-password-fields-are-filled": (
        "Enter eWork login credentials. Expected: Company ID, username, and password fields are filled"
    ),
    "submit-ework-login-expected-dashboard-is-displayed": "Submit eWork login. Expected: Dashboard is displayed",
    "open-new-customer-registration-expected-basic-customer-form-is-displayed": (
        "Open New Customer Registration. Expected: Basic customer form is displayed"
    ),
    "enter-basic-customer-information-expected-outlet-contact-channel-and-customer-type-are-filled": (
        "Enter Basic customer information. Expected: outlet, contact, channel, and customer type are filled"
    ),
    "continue-to-locations-page-expected-locations-form-is-displayed": (
        "Continue to Locations page. Expected: Locations form is displayed"
    ),
    "open-locations-page-expected-location-form-is-displayed": (
        "Open Locations page. Expected: Location form is displayed"
    ),
    "enter-customer-location-information-expected-current-location-address-and-location-dropdowns-are-filled": (
        "Enter customer Location information. Expected: current-location address and location dropdowns are filled"
    ),
    "continue-to-documents-page-expected-ktp-document-form-is-displayed": (
        "Continue to Documents page. Expected: KTP document form is displayed"
    ),
    "open-documents-page-expected-ktp-form-is-displayed": (
        "Open Documents page. Expected: KTP form is displayed"
    ),
    "enter-ktp-document-information-expected-ktp-number-is-filled-and-attachment-preview-is-displayed": (
        "Enter KTP document information. Expected: KTP number is filled and attachment preview is displayed"
    ),
    "open-signature-page-expected-signature-canvas-is-displayed": (
        "Open signature page. Expected: Signature canvas is displayed"
    ),
    "sign-and-submit-customer-registration-expected-success-message-is-displayed": (
        "Sign and submit customer registration. Expected: Success message is displayed"
    ),
    "open-new-customer-list-expected-new-customer-list-page-is-displayed": (
        "Open New Customer List. Expected: New Customer List page is displayed"
    ),
    "verify-created-customer-card-expected-name-address-and-customer-type-match-submitted-data": (
        "Verify created customer card. Expected: name, address, and customer type match submitted data"
    ),
}


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


def _screenshot_step_title(path: Path) -> str:
    slug = path.stem.split("-", 1)[-1]
    if slug in SCREENSHOT_STEP_TITLES:
        return SCREENSHOT_STEP_TITLES[slug]
    action, separator, expected = slug.partition("-expected-")
    title = _humanize_slug(action)
    if separator:
        return f"{title}. Expected: {_humanize_slug(expected)}"
    return title


def _inputs_for_screenshot(path: Path, flow_inputs: dict[str, object] | None) -> dict[str, object] | None:
    if not flow_inputs:
        return None

    slug = path.stem.split("-", 1)[-1]
    if any(
        marker in slug
        for marker in (
            "enter-ework-login-credentials",
            "enter-basic-customer-information",
            "enter-customer-location-information",
            "verify-created-customer-card",
        )
    ):
        return flow_inputs

    if "enter-ktp-document-information" in slug:
        return _fields_subset(flow_inputs, excluded={"Signature"})
    if "sign-and-submit-customer-registration" in slug:
        return _fields_subset(flow_inputs, included={"Signature"})
    return None


def _fields_subset(
    payload: dict[str, object],
    *,
    included: set[str] | None = None,
    excluded: set[str] | None = None,
) -> dict[str, object] | None:
    fields = payload.get("fields")
    if not isinstance(fields, dict):
        return payload

    subset = {
        str(key): value
        for key, value in fields.items()
        if (included is None or str(key) in included) and (excluded is None or str(key) not in excluded)
    }
    return {"fields": subset} if subset else None


def _evidence_payload_name(payload: dict[str, object] | None) -> str:
    if not payload:
        return "Inputs"
    if "expected_card" in payload and "fields" not in payload:
        return "Expected card"
    return "Inputs"


def _humanize_slug(value: str) -> str:
    words = value.replace("-", " ").split()
    return " ".join(_humanize_word(word) for word in words)


def _humanize_word(word: str) -> str:
    normalized = word.lower()
    if normalized == "ework":
        return "eWork"
    if normalized in {"id", "ktp"}:
        return normalized.upper()
    return normalized.title()


def _tail(value: str) -> str:
    if len(value) <= MAX_FAILURE_OUTPUT_CHARS:
        return value
    return value[-MAX_FAILURE_OUTPUT_CHARS:]
