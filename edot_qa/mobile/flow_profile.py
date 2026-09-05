from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final


# Captured eWork SFA UI contract. Keep selectors and fixed business choices under
# source control so locator changes are reviewed with the flows that consume them.
EWORK_FLOW_VARIABLES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "EWORK_LOGIN_SCREEN_TEXT": "Login",
        "EWORK_COMPANY_ID_FIELD_ID": "id.edot.ework:id/tv_company_id",
        "EWORK_USERNAME_FIELD_ID": "id.edot.ework:id/tv_username",
        "EWORK_PASSWORD_FIELD_ID": "id.edot.ework:id/tv_password",
        "EWORK_LOGIN_BUTTON_ID": "id.edot.ework:id/btn_signin",
        "EWORK_DASHBOARD_TEXT": "Revenue",
        "EWORK_CUSTOMERS_MENU_ID": "id.edot.ework:id/home_container_menu",
        "EWORK_CUSTOMERS_MENU_TEXT": "^New Customer$",
        "EWORK_ADD_CUSTOMER_BUTTON_ID": "id.edot.ework:id/noo_label_add_new_cust",
        "EWORK_CUSTOMER_NAME_FIELD_ID": "id.edot.ework:id/noo_registration_input_outlet_name",
        "EWORK_CUSTOMER_CONTACT_FIELD_ID": "id.edot.ework:id/noo_registration_input_phone",
        "EWORK_CUSTOMER_CONTACT_PERSON_FIELD_ID": "id.edot.ework:id/noo_registration_input_contact_person",
        "EWORK_CUSTOMER_CHANNEL_FIELD_ID": "id.edot.ework:id/noo_registration_input_channel",
        "EWORK_CUSTOMER_CHANNEL_OPTION_TEXT": "Modern Trade (MT)",
        "EWORK_CUSTOMER_TYPE_FIELD_ID": "id.edot.ework:id/noo_registration_input_outlet_type",
        "EWORK_CUSTOMER_TYPE_OPTION_TEXT": "Semi Grosir",
        "EWORK_CUSTOMER_BASIC_CONTINUE_BUTTON_ID": "id.edot.ework:id/noo_registration_action_submit",
        "EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID": "id.edot.ework:id/noo_registration_input_address_type",
        "EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT": "Delivery Address",
        "EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID": "id.edot.ework:id/noo_registration_container_use_my_current_location",
        "EWORK_CUSTOMER_PROVINCE_FIELD_TEXT": "Choose Province",
        "EWORK_CUSTOMER_PROVINCE_OPTION_TEXT": "DKI JAKARTA",
        "EWORK_CUSTOMER_CITY_FIELD_TEXT": "Choose City",
        "EWORK_CUSTOMER_CITY_OPTION_TEXT": "JAKARTA BARAT",
        "EWORK_CUSTOMER_DISTRICT_FIELD_TEXT": "Choose District",
        "EWORK_CUSTOMER_DISTRICT_OPTION_TEXT": "KEBON JERUK",
        "EWORK_CUSTOMER_SUBDISTRICT_FIELD_TEXT": "Choose Sub district",
        "EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT": "KEBON JERUK",
        "EWORK_CUSTOMER_POSTAL_CODE_FIELD_TEXT": "Choose Postal code",
        "EWORK_CUSTOMER_POSTAL_CODE_OPTION_TEXT": "11530",
        "EWORK_CUSTOMER_ADDRESS_FIELD_ID": "id.edot.ework:id/noo_registration_input_address",
        "EWORK_CUSTOMER_KTP_FIELD_ID": "id.edot.ework:id/update_info_item_input_value",
        "EWORK_CUSTOMER_UPLOAD_BUTTON_ID": "id.edot.ework:id/btn_upload",
        "EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID": "id.edot.ework:id/btn_capture",
        "EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID": "id.edot.ework:id/noo_registration_doc_action_continue",
        "EWORK_CUSTOMER_SIGNATURE_TITLE_TEXT": "Approval Signature",
        "EWORK_CUSTOMER_SIGNATURE_VIEW_ID": "id.edot.ework:id/signature_view",
        "EWORK_CUSTOMER_SAVE_BUTTON_ID": "id.edot.ework:id/update_info_action_submit",
        "EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID": "id.edot.ework:id/btn_positive",
        "EWORK_CUSTOMER_SUCCESS_TEXT": "Data Saved Successfully",
        "EWORK_CUSTOMER_SUCCESS_CONTINUE_BUTTON_ID": "id.edot.ework:id/btn_success_continue",
    }
)

DELIBERATE_WRONG_PASSWORD_FIELD_ID: Final = "id.edot.ework:id/edot_deliberate_missing_password"

