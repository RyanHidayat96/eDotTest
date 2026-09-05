from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from edot_qa.config import DEFAULT_ALLURE_RESULTS, ROOT_DIR
from edot_qa.handoff import DEFAULT_COMPANY_HANDOFF_PATH, read_company_handoff


try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


DEFAULT_MAESTRO_FLOW_DIR = ROOT_DIR / "mobile" / "flows"
DEFAULT_MAESTRO_OUTPUT_DIR = ROOT_DIR / "artifacts" / "maestro"
DEFAULT_EWORK_STORAGE_STATE = ROOT_DIR / "artifacts" / "auth" / "ework_session_state.json"
DELIBERATE_WRONG_PASSWORD_FIELD_ID = "id.edot.ework:id/edot_deliberate_missing_password"


@dataclass(frozen=True)
class MobileSettings:
    maestro_cli: str
    adb_command: str
    mobile_device_id: str | None
    mobile_flow_timeout_seconds: int
    edot_live: bool
    prefer_company_handoff: bool
    ework_app_id: str | None
    ework_email: str | None = field(repr=False)
    ework_password: str | None = field(repr=False)
    ework_company_name: str | None
    ework_company_code: str | None
    ework_login_screen_text: str | None
    ework_company_id_field_id: str | None
    ework_username_field_id: str | None
    ework_password_field_id: str | None
    ework_login_button_id: str | None
    ework_dashboard_text: str | None
    ework_customers_menu_id: str | None
    ework_customers_menu_text: str | None
    ework_add_customer_button_id: str | None
    ework_customer_name_field_id: str | None
    ework_customer_contact_field_id: str | None
    ework_customer_contact_person_field_id: str | None
    ework_customer_channel_field_id: str | None
    ework_customer_channel_option_text: str | None
    ework_customer_type_field_id: str | None
    ework_customer_type_option_text: str | None
    ework_customer_basic_continue_button_id: str | None
    ework_customer_address_type_field_id: str | None
    ework_customer_address_type_option_text: str | None
    ework_customer_current_location_button_id: str | None
    ework_customer_location_apply_button_id: str | None
    ework_customer_province_field_text: str | None
    ework_customer_province_option_text: str | None
    ework_customer_city_field_text: str | None
    ework_customer_city_option_text: str | None
    ework_customer_district_field_text: str | None
    ework_customer_district_option_text: str | None
    ework_customer_subdistrict_field_text: str | None
    ework_customer_subdistrict_option_text: str | None
    ework_customer_postal_code_field_text: str | None
    ework_customer_postal_code_option_text: str | None
    ework_customer_address_field_id: str | None
    ework_customer_ktp_field_id: str | None
    ework_customer_upload_button_id: str | None
    ework_customer_camera_capture_button_id: str | None
    ework_customer_document_submit_button_id: str | None
    ework_customer_signature_title_text: str | None
    ework_customer_signature_view_id: str | None
    ework_customer_save_button_id: str | None
    ework_customer_save_confirm_button_id: str | None
    ework_customer_success_text: str | None
    ework_customer_success_continue_button_id: str | None
    ework_customer_search_field_id: str | None
    maestro_flow_dir: Path
    maestro_output_dir: Path
    allure_results_dir: Path
    company_handoff_path: Path
    ework_storage_state_path: Path

    @property
    def has_ework_credentials(self) -> bool:
        return bool(self.ework_email and self.ework_password)

    @property
    def has_app_id(self) -> bool:
        return bool(self.ework_app_id)

    @property
    def has_login_selectors(self) -> bool:
        return bool(
            self.ework_login_screen_text
            and self.ework_company_id_field_id
            and self.ework_username_field_id
            and self.ework_password_field_id
            and self.ework_login_button_id
            and self.ework_dashboard_text
        )

    def missing_login_requirements(self) -> list[str]:
        requirements = {
            "EWORK_APP_ID": self.ework_app_id,
            "EWORK_COMPANY_CODE": self.ework_company_code,
            "EWORK_EMAIL": self.ework_email,
            "EWORK_PASSWORD": self.ework_password,
            "EWORK_LOGIN_SCREEN_TEXT": self.ework_login_screen_text,
            "EWORK_COMPANY_ID_FIELD_ID": self.ework_company_id_field_id,
            "EWORK_USERNAME_FIELD_ID": self.ework_username_field_id,
            "EWORK_PASSWORD_FIELD_ID": self.ework_password_field_id,
            "EWORK_LOGIN_BUTTON_ID": self.ework_login_button_id,
            "EWORK_DASHBOARD_TEXT": self.ework_dashboard_text,
        }
        return [key for key, value in requirements.items() if not value]

    def missing_customer_requirements(self) -> list[str]:
        requirements = {
            "EWORK_CUSTOMERS_MENU_ID": self.ework_customers_menu_id,
            "EWORK_CUSTOMERS_MENU_TEXT": self.ework_customers_menu_text,
            "EWORK_ADD_CUSTOMER_BUTTON_ID": self.ework_add_customer_button_id,
            "EWORK_CUSTOMER_NAME_FIELD_ID": self.ework_customer_name_field_id,
            "EWORK_CUSTOMER_CONTACT_FIELD_ID": self.ework_customer_contact_field_id,
            "EWORK_CUSTOMER_CONTACT_PERSON_FIELD_ID": self.ework_customer_contact_person_field_id,
            "EWORK_CUSTOMER_CHANNEL_FIELD_ID": self.ework_customer_channel_field_id,
            "EWORK_CUSTOMER_CHANNEL_OPTION_TEXT": self.ework_customer_channel_option_text,
            "EWORK_CUSTOMER_TYPE_FIELD_ID": self.ework_customer_type_field_id,
            "EWORK_CUSTOMER_TYPE_OPTION_TEXT": self.ework_customer_type_option_text,
            "EWORK_CUSTOMER_BASIC_CONTINUE_BUTTON_ID": self.ework_customer_basic_continue_button_id,
            "EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID": self.ework_customer_address_type_field_id,
            "EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT": self.ework_customer_address_type_option_text,
            "EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID": self.ework_customer_current_location_button_id,
            "EWORK_CUSTOMER_PROVINCE_FIELD_TEXT": self.ework_customer_province_field_text,
            "EWORK_CUSTOMER_PROVINCE_OPTION_TEXT": self.ework_customer_province_option_text,
            "EWORK_CUSTOMER_CITY_FIELD_TEXT": self.ework_customer_city_field_text,
            "EWORK_CUSTOMER_CITY_OPTION_TEXT": self.ework_customer_city_option_text,
            "EWORK_CUSTOMER_DISTRICT_FIELD_TEXT": self.ework_customer_district_field_text,
            "EWORK_CUSTOMER_DISTRICT_OPTION_TEXT": self.ework_customer_district_option_text,
            "EWORK_CUSTOMER_SUBDISTRICT_FIELD_TEXT": self.ework_customer_subdistrict_field_text,
            "EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT": self.ework_customer_subdistrict_option_text,
            "EWORK_CUSTOMER_POSTAL_CODE_FIELD_TEXT": self.ework_customer_postal_code_field_text,
            "EWORK_CUSTOMER_POSTAL_CODE_OPTION_TEXT": self.ework_customer_postal_code_option_text,
            "EWORK_CUSTOMER_ADDRESS_FIELD_ID": self.ework_customer_address_field_id,
            "EWORK_CUSTOMER_KTP_FIELD_ID": self.ework_customer_ktp_field_id,
            "EWORK_CUSTOMER_UPLOAD_BUTTON_ID": self.ework_customer_upload_button_id,
            "EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID": self.ework_customer_camera_capture_button_id,
            "EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID": self.ework_customer_document_submit_button_id,
            "EWORK_CUSTOMER_SIGNATURE_TITLE_TEXT": self.ework_customer_signature_title_text,
            "EWORK_CUSTOMER_SIGNATURE_VIEW_ID": self.ework_customer_signature_view_id,
            "EWORK_CUSTOMER_SAVE_BUTTON_ID": self.ework_customer_save_button_id,
            "EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID": self.ework_customer_save_confirm_button_id,
            "EWORK_CUSTOMER_SUCCESS_TEXT": self.ework_customer_success_text,
            "EWORK_CUSTOMER_SUCCESS_CONTINUE_BUTTON_ID": self.ework_customer_success_continue_button_id,
        }
        missing = self.missing_login_requirements()
        missing.extend(key for key, value in requirements.items() if not value)
        return missing

    def ensure_runtime_dirs(self) -> None:
        self.maestro_output_dir.mkdir(parents=True, exist_ok=True)
        self.allure_results_dir.mkdir(parents=True, exist_ok=True)

    def as_safe_dict(self) -> dict[str, str]:
        return {
            "MAESTRO_CLI": self.maestro_cli,
            "ADB_COMMAND": self.adb_command,
            "MOBILE_DEVICE_ID": self.mobile_device_id or "<auto>",
            "MOBILE_FLOW_TIMEOUT_SECONDS": str(self.mobile_flow_timeout_seconds),
            "EDOT_LIVE": str(self.edot_live).lower(),
            "EWORK_PREFER_HANDOFF": str(self.prefer_company_handoff).lower(),
            "EWORK_APP_ID": self.ework_app_id or "<missing>",
            "EWORK_EMAIL": "<set>" if self.ework_email else "<missing>",
            "EWORK_PASSWORD": "<set>" if self.ework_password else "<missing>",
            "EWORK_COMPANY_NAME": self.ework_company_name or "<missing>",
            "EWORK_COMPANY_CODE": "<set>" if self.ework_company_code else "<missing>",
            "EWORK_LOGIN_SCREEN_TEXT": self.ework_login_screen_text or "<missing>",
            "EWORK_COMPANY_ID_FIELD_ID": self.ework_company_id_field_id or "<missing>",
            "EWORK_USERNAME_FIELD_ID": self.ework_username_field_id or "<missing>",
            "EWORK_PASSWORD_FIELD_ID": self.ework_password_field_id or "<missing>",
            "EWORK_LOGIN_BUTTON_ID": self.ework_login_button_id or "<missing>",
            "EWORK_DASHBOARD_TEXT": self.ework_dashboard_text or "<missing>",
            "EWORK_CUSTOMERS_MENU_ID": self.ework_customers_menu_id or "<missing>",
            "EWORK_CUSTOMERS_MENU_TEXT": self.ework_customers_menu_text or "<missing>",
            "EWORK_ADD_CUSTOMER_BUTTON_ID": self.ework_add_customer_button_id or "<missing>",
            "EWORK_CUSTOMER_NAME_FIELD_ID": self.ework_customer_name_field_id or "<missing>",
            "EWORK_CUSTOMER_CONTACT_FIELD_ID": self.ework_customer_contact_field_id or "<missing>",
            "EWORK_CUSTOMER_CONTACT_PERSON_FIELD_ID": self.ework_customer_contact_person_field_id or "<missing>",
            "EWORK_CUSTOMER_CHANNEL_FIELD_ID": self.ework_customer_channel_field_id or "<missing>",
            "EWORK_CUSTOMER_CHANNEL_OPTION_TEXT": self.ework_customer_channel_option_text or "<missing>",
            "EWORK_CUSTOMER_TYPE_FIELD_ID": self.ework_customer_type_field_id or "<missing>",
            "EWORK_CUSTOMER_TYPE_OPTION_TEXT": self.ework_customer_type_option_text or "<missing>",
            "EWORK_CUSTOMER_BASIC_CONTINUE_BUTTON_ID": self.ework_customer_basic_continue_button_id or "<missing>",
            "EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID": self.ework_customer_address_type_field_id or "<missing>",
            "EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT": self.ework_customer_address_type_option_text or "<missing>",
            "EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID": self.ework_customer_current_location_button_id or "<missing>",
            "EWORK_CUSTOMER_LOCATION_APPLY_BUTTON_ID": self.ework_customer_location_apply_button_id or "<missing>",
            "EWORK_CUSTOMER_PROVINCE_FIELD_TEXT": self.ework_customer_province_field_text or "<missing>",
            "EWORK_CUSTOMER_PROVINCE_OPTION_TEXT": self.ework_customer_province_option_text or "<missing>",
            "EWORK_CUSTOMER_CITY_FIELD_TEXT": self.ework_customer_city_field_text or "<missing>",
            "EWORK_CUSTOMER_CITY_OPTION_TEXT": self.ework_customer_city_option_text or "<missing>",
            "EWORK_CUSTOMER_DISTRICT_FIELD_TEXT": self.ework_customer_district_field_text or "<missing>",
            "EWORK_CUSTOMER_DISTRICT_OPTION_TEXT": self.ework_customer_district_option_text or "<missing>",
            "EWORK_CUSTOMER_SUBDISTRICT_FIELD_TEXT": self.ework_customer_subdistrict_field_text or "<missing>",
            "EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT": self.ework_customer_subdistrict_option_text or "<missing>",
            "EWORK_CUSTOMER_POSTAL_CODE_FIELD_TEXT": self.ework_customer_postal_code_field_text or "<missing>",
            "EWORK_CUSTOMER_POSTAL_CODE_OPTION_TEXT": self.ework_customer_postal_code_option_text or "<missing>",
            "EWORK_CUSTOMER_ADDRESS_FIELD_ID": self.ework_customer_address_field_id or "<missing>",
            "EWORK_CUSTOMER_KTP_FIELD_ID": self.ework_customer_ktp_field_id or "<missing>",
            "EWORK_CUSTOMER_UPLOAD_BUTTON_ID": self.ework_customer_upload_button_id or "<missing>",
            "EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID": self.ework_customer_camera_capture_button_id or "<missing>",
            "EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID": self.ework_customer_document_submit_button_id or "<missing>",
            "EWORK_CUSTOMER_SIGNATURE_TITLE_TEXT": self.ework_customer_signature_title_text or "<missing>",
            "EWORK_CUSTOMER_SIGNATURE_VIEW_ID": self.ework_customer_signature_view_id or "<missing>",
            "EWORK_CUSTOMER_SAVE_BUTTON_ID": self.ework_customer_save_button_id or "<missing>",
            "EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID": self.ework_customer_save_confirm_button_id or "<missing>",
            "EWORK_CUSTOMER_SUCCESS_TEXT": self.ework_customer_success_text or "<missing>",
            "EWORK_CUSTOMER_SUCCESS_CONTINUE_BUTTON_ID": self.ework_customer_success_continue_button_id or "<missing>",
            "EWORK_CUSTOMER_SEARCH_FIELD_ID": self.ework_customer_search_field_id or "<missing>",
            "MAESTRO_FLOW_DIR": str(self.maestro_flow_dir),
            "MAESTRO_OUTPUT_DIR": str(self.maestro_output_dir),
            "ALLURE_RESULTS_DIR": str(self.allure_results_dir),
            "EWORK_COMPANY_HANDOFF_PATH": str(self.company_handoff_path),
            "EWORK_STORAGE_STATE": str(self.ework_storage_state_path),
        }

    def maestro_environment(self, extra_values: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env.update(self.maestro_variables(extra_values))
        return env

    def deliberate_wrong_password_field_override(self) -> dict[str, str]:
        return {"EWORK_PASSWORD_FIELD_ID": DELIBERATE_WRONG_PASSWORD_FIELD_ID}

    def maestro_variables(self, extra_values: dict[str, str] | None = None) -> dict[str, str]:
        optional_values = {
            "EWORK_APP_ID": self.ework_app_id,
            "EWORK_EMAIL": self.ework_email,
            "EWORK_PASSWORD": self.ework_password,
            "EWORK_COMPANY_NAME": self.ework_company_name,
            "EWORK_COMPANY_CODE": self.ework_company_code,
            "EWORK_LOGIN_SCREEN_TEXT": self.ework_login_screen_text,
            "EWORK_COMPANY_ID_FIELD_ID": self.ework_company_id_field_id,
            "EWORK_USERNAME_FIELD_ID": self.ework_username_field_id,
            "EWORK_PASSWORD_FIELD_ID": self.ework_password_field_id,
            "EWORK_LOGIN_BUTTON_ID": self.ework_login_button_id,
            "EWORK_DASHBOARD_TEXT": self.ework_dashboard_text,
            "EWORK_CUSTOMERS_MENU_ID": self.ework_customers_menu_id,
            "EWORK_CUSTOMERS_MENU_TEXT": self.ework_customers_menu_text,
            "EWORK_ADD_CUSTOMER_BUTTON_ID": self.ework_add_customer_button_id,
            "EWORK_CUSTOMER_NAME_FIELD_ID": self.ework_customer_name_field_id,
            "EWORK_CUSTOMER_CONTACT_FIELD_ID": self.ework_customer_contact_field_id,
            "EWORK_CUSTOMER_CONTACT_PERSON_FIELD_ID": self.ework_customer_contact_person_field_id,
            "EWORK_CUSTOMER_CHANNEL_FIELD_ID": self.ework_customer_channel_field_id,
            "EWORK_CUSTOMER_CHANNEL_OPTION_TEXT": self.ework_customer_channel_option_text,
            "EWORK_CUSTOMER_TYPE_FIELD_ID": self.ework_customer_type_field_id,
            "EWORK_CUSTOMER_TYPE_OPTION_TEXT": self.ework_customer_type_option_text,
            "EWORK_CUSTOMER_BASIC_CONTINUE_BUTTON_ID": self.ework_customer_basic_continue_button_id,
            "EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID": self.ework_customer_address_type_field_id,
            "EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT": self.ework_customer_address_type_option_text,
            "EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID": self.ework_customer_current_location_button_id,
            "EWORK_CUSTOMER_LOCATION_APPLY_BUTTON_ID": self.ework_customer_location_apply_button_id,
            "EWORK_CUSTOMER_PROVINCE_FIELD_TEXT": self.ework_customer_province_field_text,
            "EWORK_CUSTOMER_PROVINCE_OPTION_TEXT": self.ework_customer_province_option_text,
            "EWORK_CUSTOMER_CITY_FIELD_TEXT": self.ework_customer_city_field_text,
            "EWORK_CUSTOMER_CITY_OPTION_TEXT": self.ework_customer_city_option_text,
            "EWORK_CUSTOMER_DISTRICT_FIELD_TEXT": self.ework_customer_district_field_text,
            "EWORK_CUSTOMER_DISTRICT_OPTION_TEXT": self.ework_customer_district_option_text,
            "EWORK_CUSTOMER_SUBDISTRICT_FIELD_TEXT": self.ework_customer_subdistrict_field_text,
            "EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT": self.ework_customer_subdistrict_option_text,
            "EWORK_CUSTOMER_POSTAL_CODE_FIELD_TEXT": self.ework_customer_postal_code_field_text,
            "EWORK_CUSTOMER_POSTAL_CODE_OPTION_TEXT": self.ework_customer_postal_code_option_text,
            "EWORK_CUSTOMER_ADDRESS_FIELD_ID": self.ework_customer_address_field_id,
            "EWORK_CUSTOMER_KTP_FIELD_ID": self.ework_customer_ktp_field_id,
            "EWORK_CUSTOMER_UPLOAD_BUTTON_ID": self.ework_customer_upload_button_id,
            "EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID": self.ework_customer_camera_capture_button_id,
            "EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID": self.ework_customer_document_submit_button_id,
            "EWORK_CUSTOMER_SIGNATURE_TITLE_TEXT": self.ework_customer_signature_title_text,
            "EWORK_CUSTOMER_SIGNATURE_VIEW_ID": self.ework_customer_signature_view_id,
            "EWORK_CUSTOMER_SAVE_BUTTON_ID": self.ework_customer_save_button_id,
            "EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID": self.ework_customer_save_confirm_button_id,
            "EWORK_CUSTOMER_SUCCESS_TEXT": self.ework_customer_success_text,
            "EWORK_CUSTOMER_SUCCESS_CONTINUE_BUTTON_ID": self.ework_customer_success_continue_button_id,
            "EWORK_CUSTOMER_SEARCH_FIELD_ID": self.ework_customer_search_field_id,
        }
        variables = {}
        for key, value in optional_values.items():
            if value:
                variables[key] = value
        for key, value in (extra_values or {}).items():
            if value:
                variables[key] = value
        return variables


def load_mobile_settings(*, prefer_handoff: bool | None = None) -> MobileSettings:
    _load_dotenv()
    handoff_path = _path_from_env("EWORK_COMPANY_HANDOFF_PATH", DEFAULT_COMPANY_HANDOFF_PATH)
    handoff = read_company_handoff(handoff_path)
    prefer_company_handoff = _bool_from_env("EWORK_PREFER_HANDOFF") if prefer_handoff is None else prefer_handoff
    handoff_username = handoff.mobile_username if handoff else None
    handoff_name = handoff.company_name if handoff else None
    handoff_code = handoff.company_code if handoff else None
    return MobileSettings(
        maestro_cli=os.getenv("MAESTRO_CLI", "maestro"),
        adb_command=os.getenv("ADB_COMMAND", "adb"),
        mobile_device_id=os.getenv("MOBILE_DEVICE_ID") or None,
        mobile_flow_timeout_seconds=_int_from_env("MOBILE_FLOW_TIMEOUT_SECONDS", 300),
        edot_live=_bool_from_env("EDOT_LIVE"),
        prefer_company_handoff=prefer_company_handoff,
        ework_app_id=os.getenv("EWORK_APP_ID") or None,
        ework_email=_company_identity_value("EWORK_EMAIL", handoff_username, prefer_company_handoff),
        ework_password=os.getenv("EWORK_PASSWORD") or None,
        ework_company_name=_company_identity_value("EWORK_COMPANY_NAME", handoff_name, prefer_company_handoff),
        ework_company_code=_company_identity_value("EWORK_COMPANY_CODE", handoff_code, prefer_company_handoff),
        ework_login_screen_text=os.getenv("EWORK_LOGIN_SCREEN_TEXT") or None,
        ework_company_id_field_id=os.getenv("EWORK_COMPANY_ID_FIELD_ID") or None,
        ework_username_field_id=os.getenv("EWORK_USERNAME_FIELD_ID") or None,
        ework_password_field_id=os.getenv("EWORK_PASSWORD_FIELD_ID") or None,
        ework_login_button_id=os.getenv("EWORK_LOGIN_BUTTON_ID") or None,
        ework_dashboard_text=os.getenv("EWORK_DASHBOARD_TEXT") or None,
        ework_customers_menu_id=os.getenv("EWORK_CUSTOMERS_MENU_ID") or None,
        ework_customers_menu_text=os.getenv("EWORK_CUSTOMERS_MENU_TEXT") or None,
        ework_add_customer_button_id=os.getenv("EWORK_ADD_CUSTOMER_BUTTON_ID") or None,
        ework_customer_name_field_id=os.getenv("EWORK_CUSTOMER_NAME_FIELD_ID") or None,
        ework_customer_contact_field_id=os.getenv("EWORK_CUSTOMER_CONTACT_FIELD_ID") or None,
        ework_customer_contact_person_field_id=os.getenv("EWORK_CUSTOMER_CONTACT_PERSON_FIELD_ID") or None,
        ework_customer_channel_field_id=os.getenv("EWORK_CUSTOMER_CHANNEL_FIELD_ID") or None,
        ework_customer_channel_option_text=os.getenv("EWORK_CUSTOMER_CHANNEL_OPTION_TEXT") or None,
        ework_customer_type_field_id=os.getenv("EWORK_CUSTOMER_TYPE_FIELD_ID") or None,
        ework_customer_type_option_text=os.getenv("EWORK_CUSTOMER_TYPE_OPTION_TEXT") or None,
        ework_customer_basic_continue_button_id=os.getenv("EWORK_CUSTOMER_BASIC_CONTINUE_BUTTON_ID") or None,
        ework_customer_address_type_field_id=os.getenv("EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID") or None,
        ework_customer_address_type_option_text=os.getenv("EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT") or None,
        ework_customer_current_location_button_id=os.getenv("EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID") or None,
        ework_customer_location_apply_button_id=os.getenv("EWORK_CUSTOMER_LOCATION_APPLY_BUTTON_ID") or None,
        ework_customer_province_field_text=os.getenv("EWORK_CUSTOMER_PROVINCE_FIELD_TEXT") or None,
        ework_customer_province_option_text=os.getenv("EWORK_CUSTOMER_PROVINCE_OPTION_TEXT") or None,
        ework_customer_city_field_text=os.getenv("EWORK_CUSTOMER_CITY_FIELD_TEXT") or None,
        ework_customer_city_option_text=os.getenv("EWORK_CUSTOMER_CITY_OPTION_TEXT") or None,
        ework_customer_district_field_text=os.getenv("EWORK_CUSTOMER_DISTRICT_FIELD_TEXT") or None,
        ework_customer_district_option_text=os.getenv("EWORK_CUSTOMER_DISTRICT_OPTION_TEXT") or None,
        ework_customer_subdistrict_field_text=os.getenv("EWORK_CUSTOMER_SUBDISTRICT_FIELD_TEXT") or None,
        ework_customer_subdistrict_option_text=os.getenv("EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT") or None,
        ework_customer_postal_code_field_text=os.getenv("EWORK_CUSTOMER_POSTAL_CODE_FIELD_TEXT") or None,
        ework_customer_postal_code_option_text=os.getenv("EWORK_CUSTOMER_POSTAL_CODE_OPTION_TEXT") or None,
        ework_customer_address_field_id=os.getenv("EWORK_CUSTOMER_ADDRESS_FIELD_ID") or None,
        ework_customer_ktp_field_id=os.getenv("EWORK_CUSTOMER_KTP_FIELD_ID") or None,
        ework_customer_upload_button_id=os.getenv("EWORK_CUSTOMER_UPLOAD_BUTTON_ID") or None,
        ework_customer_camera_capture_button_id=os.getenv("EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID") or None,
        ework_customer_document_submit_button_id=os.getenv("EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID") or None,
        ework_customer_signature_title_text=os.getenv("EWORK_CUSTOMER_SIGNATURE_TITLE_TEXT") or None,
        ework_customer_signature_view_id=os.getenv("EWORK_CUSTOMER_SIGNATURE_VIEW_ID") or None,
        ework_customer_save_button_id=os.getenv("EWORK_CUSTOMER_SAVE_BUTTON_ID") or None,
        ework_customer_save_confirm_button_id=os.getenv("EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID") or None,
        ework_customer_success_text=os.getenv("EWORK_CUSTOMER_SUCCESS_TEXT") or None,
        ework_customer_success_continue_button_id=os.getenv("EWORK_CUSTOMER_SUCCESS_CONTINUE_BUTTON_ID") or None,
        ework_customer_search_field_id=os.getenv("EWORK_CUSTOMER_SEARCH_FIELD_ID") or None,
        maestro_flow_dir=_path_from_env("MAESTRO_FLOW_DIR", DEFAULT_MAESTRO_FLOW_DIR),
        maestro_output_dir=_path_from_env("MAESTRO_OUTPUT_DIR", DEFAULT_MAESTRO_OUTPUT_DIR),
        allure_results_dir=_path_from_env("ALLURE_RESULTS_DIR", DEFAULT_ALLURE_RESULTS),
        company_handoff_path=handoff_path,
        ework_storage_state_path=_path_from_env("EWORK_STORAGE_STATE", DEFAULT_EWORK_STORAGE_STATE),
    )


def _load_dotenv() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def _path_from_env(name: str, default: Path) -> Path:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    path = Path(raw_value)
    return path if path.is_absolute() else ROOT_DIR / path


def _company_identity_value(name: str, handoff_value: str | None, prefer_handoff: bool) -> str | None:
    env_value = os.getenv(name) or None
    if prefer_handoff and handoff_value:
        return handoff_value
    return env_value or handoff_value


def _bool_from_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _int_from_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)
