from __future__ import annotations

from pathlib import Path

from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.customer import MobileCustomerData
from edot_qa.mobile.device import (
    MobileDevice,
    ScrollSearchResult,
    capture_device_screenshot,
    scroll_list_to_end_and_find_texts,
    visible_texts_by_resource_id,
)
from edot_qa.mobile.maestro import MaestroResult
from edot_qa.reporting.allure_helpers import allure_step, attach_json, attach_png


CUSTOMER_CARD_ADDRESS_MARKER = "__EWORK_CUSTOMER_CARD_ADDRESS__="
CUSTOMER_CARD_NAME_ID = "id.edot.ework:id/tv_name"
CUSTOMER_CARD_ADDRESS_ID = "id.edot.ework:id/tv_address"
CUSTOMER_CARD_TYPE_ID = "id.edot.ework:id/tv_first_customer_group"
CUSTOMER_CARD_RESOURCE_IDS = [
    CUSTOMER_CARD_NAME_ID,
    CUSTOMER_CARD_ADDRESS_ID,
    CUSTOMER_CARD_TYPE_ID,
]


def customer_card_address_from_maestro_result(result: MaestroResult, log_root: Path | None = None) -> str:
    value = customer_card_address_from_maestro_text(f"{result.stdout}\n{result.stderr}")
    if value:
        return value

    value = customer_card_address_from_maestro_logs(log_root or Path.home() / ".maestro" / "tests")
    if value:
        return value

    raise AssertionError("Created customer card address marker not found in Maestro output")


def customer_card_address_from_maestro_stdout(stdout: str) -> str:
    value = customer_card_address_from_maestro_text(stdout)
    if value:
        return value
    raise AssertionError("Created customer card address marker not found in Maestro output")


def customer_card_address_from_maestro_logs(log_root: Path) -> str | None:
    if not log_root.is_dir():
        return None
    log_paths = sorted(log_root.rglob("maestro.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    for log_path in log_paths[:20]:
        if "create_customer" not in str(log_path):
            continue
        value = customer_card_address_from_maestro_text(log_path.read_text(encoding="utf-8", errors="replace"))
        if value:
            return value
    return None


def customer_card_address_from_maestro_text(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if CUSTOMER_CARD_ADDRESS_MARKER not in line:
            continue
        stripped_line = line.strip()
        log_message_index = stripped_line.find("logMessages=[")
        marker_index = stripped_line.find(CUSTOMER_CARD_ADDRESS_MARKER, log_message_index)
        if log_message_index >= 0 and marker_index >= 0:
            value = stripped_line[marker_index + len(CUSTOMER_CARD_ADDRESS_MARKER) :].split(
                "], insight=",
                1,
            )[0].strip()
            if value:
                return value
        if "console.log(" in stripped_line or "output.customerAddress" in stripped_line:
            continue
        if not (stripped_line.startswith(CUSTOMER_CARD_ADDRESS_MARKER) or "JsConsole:" in stripped_line):
            continue
        value = line.split(CUSTOMER_CARD_ADDRESS_MARKER, 1)[1].strip()
        if value and "COMPLETED" not in value:
            return value
    return None


def find_created_customer_card(
    customer: MobileCustomerData,
    *,
    customer_card_address: str,
    settings: MobileSettings,
    device: MobileDevice,
) -> ScrollSearchResult | dict[str, object]:
    with allure_step(
        "Find created customer card from list bottom",
        data={
            "customer_name": customer.name,
            "customer_card_address": customer_card_address,
            "customer_type": settings.ework_customer_type_option_text,
            "bottom_timeout_seconds": 40,
            "search_timeout_seconds": 40,
            "max_up_swipes": 4,
            "search_identity": "customer_name",
        },
        screenshot=False,
    ):
        expected_card_texts = [
            customer.name,
            customer_card_address,
            settings.ework_customer_type_option_text or "",
        ]
        pre_scroll_locator_texts = visible_texts_by_resource_id(
            CUSTOMER_CARD_RESOURCE_IDS,
            settings.adb_command,
            device_id=settings.mobile_device_id or device.serial,
            timeout_seconds=10,
        )
        attach_json("customer-card-locators-before-scroll", pre_scroll_locator_texts)
        _attach_customer_list_screenshot("customer-card-before-scroll", settings, device)
        if customer_card_values_visible(
            pre_scroll_locator_texts,
            customer_name=customer.name,
            customer_address=customer_card_address,
            customer_type=settings.ework_customer_type_option_text or "",
        ):
            result = {
                "reached_end": False,
                "down_swipes": 0,
                "up_swipes": 0,
                "visible_texts": pre_scroll_locator_texts,
                "skipped_scroll": True,
            }
            attach_json("customer-list-scroll-search", result)
            _attach_customer_list_screenshot("customer-card-visible-before-scroll", settings, device)
            return result

        scroll_result = scroll_list_to_end_and_find_texts(
            expected_card_texts,
            settings.adb_command,
            device_id=settings.mobile_device_id or device.serial,
            bottom_timeout_seconds=40,
            search_timeout_seconds=40,
            max_up_swipes=4,
        )
        attach_json(
            "customer-list-scroll-search",
            {
                "reached_end": scroll_result.reached_end,
                "down_swipes": scroll_result.down_swipes,
                "up_swipes": scroll_result.up_swipes,
                "visible_texts": scroll_result.visible_texts,
                "skipped_scroll": False,
            },
        )
        _attach_customer_list_screenshot("customer-card-after-scroll-search", settings, device)
        return scroll_result


def customer_card_values_visible(
    locator_texts: dict[str, list[str]],
    *,
    customer_name: str,
    customer_address: str,
    customer_type: str,
) -> bool:
    expectations = {
        CUSTOMER_CARD_NAME_ID: customer_name,
        CUSTOMER_CARD_ADDRESS_ID: customer_address,
        CUSTOMER_CARD_TYPE_ID: customer_type,
    }
    return all(
        _text_in_values(expected_text, locator_texts.get(locator_id, []))
        for locator_id, expected_text in expectations.items()
    )


def _text_in_values(expected_text: str, values: list[str]) -> bool:
    normalized_expected = _normalize_text(expected_text)
    if not normalized_expected:
        return False
    return any(normalized_expected in _normalize_text(value) for value in values)


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _attach_customer_list_screenshot(name: str, settings: MobileSettings, device: MobileDevice) -> None:
    image = capture_device_screenshot(
        settings.adb_command,
        device_id=settings.mobile_device_id or device.serial,
        timeout_seconds=5,
    )
    if image:
        attach_png(name, image)
