from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from edot_qa.reporting.allure_metadata import metadata_for_node


ROOT_DIR = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT_DIR / "test_cases" / "manual_test_cases.csv"
XLSX_PATH = ROOT_DIR / "test_cases" / "eDOT_QA_Automation_Test_Cases.xlsx"
HEADERS = [
    "Test Case ID",
    "Title / Description",
    "Precondition",
    "Test Steps",
    "Test Data (exact values)",
    "Expected Result",
    "Assertion Tier",
    "Status",
]
EXPECTED_IDS = ["WEB-TC-001", "WEB-TC-002", "WEB-TC-003", "WEB-TC-004", "WEB-TC-005", "MOB-TC-001", "MOB-TC-002"]


def test_manual_csv_has_required_columns_cases_and_blank_status() -> None:
    rows = _csv_rows()

    assert list(rows[0].keys()) == HEADERS
    assert [row["Test Case ID"] for row in rows] == EXPECTED_IDS
    assert all(row["Status"] == "" for row in rows)


def test_manual_company_create_detail_and_delete_share_same_runtime_values() -> None:
    cases = {row["Test Case ID"]: row for row in _csv_rows()}
    create_data = cases["WEB-TC-003"]["Test Data (exact values)"]
    detail_data = cases["WEB-TC-004"]["Test Data (exact values)"]
    delete_data = cases["WEB-TC-005"]["Test Data (exact values)"]

    for expected in (
        "Company Name=PT Ritel QA ${RUN_ID}",
        "Email=qa.company.${RUN_ID}@example.test",
        "Phone=81234567890",
        "Industry Type=Retail",
        "Company Type=Retailer",
        "Street Address=Jalan Sudirman No 10",
        "Postal Code=12190",
    ):
        assert expected in create_data
        assert expected in detail_data

    assert "Company Name=PT Ritel QA ${RUN_ID}" in delete_data
    assert "Company ID=<captured non-secret runtime value>" in delete_data
    assert "qa.company+${RUN_ID}@example.test" not in detail_data
    assert "qa${RUN_ID}@qa.test" not in create_data


def test_manual_step_one_validation_is_not_mislabeled_as_negative() -> None:
    cases = {row["Test Case ID"]: row for row in _csv_rows()}

    assert cases["WEB-TC-002"]["Assertion Tier"] == "Tier 1"
    assert "specific error message" not in cases["WEB-TC-002"]["Expected Result"].lower()


def test_manual_mobile_customer_case_matches_real_list_card_validation() -> None:
    cases = {row["Test Case ID"]: row for row in _csv_rows()}
    mobile_customer = cases["MOB-TC-002"]
    combined = " ".join(
        mobile_customer[column]
        for column in ("Test Steps", "Test Data (exact values)", "Expected Result")
    )
    combined_lower = combined.lower()

    assert "Use my current location" in combined
    assert "Current Location Address=<captured from app address field>" in combined
    assert "KTP=<16 digit runtime value>" in combined
    assert "Attachment=camera capture" in combined
    assert "Signature=drawn" in combined
    assert "card name equals submitted outlet name" in combined_lower
    assert "card address equals the address captured from the app" in combined_lower
    assert "card customer type equals submitted customer type" in combined_lower
    assert "Search or open created customer" not in combined
    assert "customer list/detail" not in combined


def test_manual_cases_do_not_store_secret_values() -> None:
    secret_assignment = re.compile(r"(PASSWORD|API_KEY|TOKEN|SECRET)=([^<;\s][^;\s]*)", re.IGNORECASE)
    combined = "\n".join(value for row in _csv_rows() for value in row.values())

    assert "it.QA2025" not in combined
    assert "AQ." not in combined
    assert "AIza" not in combined
    assert "sk-" not in combined
    assert secret_assignment.search(combined) is None


def test_manual_xlsx_matches_csv_headers_row_count_and_metadata() -> None:
    csv_rows = _csv_rows()
    workbook_rows = _xlsx_rows("xl/worksheets/sheet1.xml")
    metadata_text = "\n".join(value for row in _xlsx_rows("xl/worksheets/sheet2.xml") for value in row)

    assert workbook_rows[0] == HEADERS
    assert len(workbook_rows) == len(csv_rows) + 1
    assert [row[0] for row in workbook_rows[1:]] == EXPECTED_IDS
    assert "https://github.com/RyanHidayat96/TestEdot" in metadata_text


def test_automated_requirement_flows_are_traceable_to_manual_ids() -> None:
    cases = {
        "tests/web/test_login.py::test_esuite_login_shows_dashboard_greeting": "WEB-TC-001",
        "tests/web/test_create_company.py::test_create_company_three_step_wizard_with_ai_data": "WEB-TC-003",
        "tests/mobile/test_mobile_login.py::test_ework_login_displays_dashboard": "MOB-TC-001",
        "tests/mobile/test_mobile_create_customer.py::test_ework_create_customer_appears_with_correct_data": "MOB-TC-002",
    }

    for node_id, test_case_id in cases.items():
        metadata = metadata_for_node(node_id)
        assert metadata.test_case_id == test_case_id
        assert test_case_id in metadata.tags

    full_company_metadata = metadata_for_node(
        "tests/web/test_create_company.py::test_create_company_three_step_wizard_with_ai_data"
    )
    assert "WEB-TC-004" in full_company_metadata.tags
    assert "WEB-TC-005" in full_company_metadata.tags


def _csv_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == HEADERS
        return list(reader)


def _xlsx_rows(member: str) -> list[list[str]]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(XLSX_PATH) as workbook:
        root = ET.fromstring(workbook.read(member))

    rows: list[list[str]] = []
    for row in root.findall(".//main:sheetData/main:row", namespace):
        values: list[str] = []
        for cell in row.findall("main:c", namespace):
            values.append("".join(text.text or "" for text in cell.findall(".//main:t", namespace)))
        rows.append(values)
    return rows
