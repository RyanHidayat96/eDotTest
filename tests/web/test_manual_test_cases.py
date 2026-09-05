from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

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
WORKBOOK_HEADERS = [*HEADERS[:-1], "Status (leave blank)"]
EXPECTED_IDS = [
    "WEB-TC-001",
    "WEB-TC-002",
    "WEB-TC-003",
    "WEB-TC-004",
    "WEB-TC-006",
    "MOB-TC-001",
    "MOB-TC-002",
    "E2E-WEB-MOBILE-001",
    "WEB-TC-005",
]


def test_manual_csv_has_required_columns_cases_and_blank_status() -> None:
    rows = _csv_rows()

    assert list(rows[0].keys()) == HEADERS
    assert [row["Test Case ID"] for row in rows] == EXPECTED_IDS
    assert all(row["Status"] == "" for row in rows)


def test_manual_company_create_detail_and_delete_share_same_fixed_values() -> None:
    cases = {row["Test Case ID"]: row for row in _csv_rows()}
    create_data = cases["WEB-TC-003"]["Test Data (exact values)"]
    detail_data = cases["WEB-TC-004"]["Test Data (exact values)"]
    delete_data = cases["WEB-TC-005"]["Test Data (exact values)"]

    for expected in (
        "Company Name: PT Ritel Nusantara Manual QA",
        "Email: qa.ritel.nusantara@example.test",
        "Phone: 81234567890",
        "Industry Type: Retail",
        "Company Type: Retailer",
        "Street Address: Jalan Jenderal Sudirman Kav. 52-53",
        "Postal Code: 12190",
    ):
        assert expected in create_data
        assert expected in detail_data

    assert "Company Name: PT Ritel Nusantara Manual QA" in delete_data
    assert "Company ID: Company ID recorded in WEB-TC-004" in delete_data


def test_manual_cases_are_human_readable_and_automation_agnostic() -> None:
    rows = _csv_rows()
    combined = "\n".join(value for row in rows for value in row.values())
    forbidden_fragments = (
        "${",
        "<secure",
        "<captured",
        "ESUITE_",
        "EWORK_",
        "storage_state",
        "Allure",
        "runtime generated",
        "deterministic fallback",
    )

    for fragment in forbidden_fragments:
        assert fragment.casefold() not in combined.casefold()

    for row in rows:
        steps = row["Test Steps"].splitlines()
        assert len(steps) >= 2
        assert ";" not in row["Test Steps"]
        assert [int(re.match(r"^(\d+)\.\s", step).group(1)) for step in steps] == list(
            range(1, len(steps) + 1)
        )
        assert all(line.startswith("- ") for line in row["Precondition"].splitlines())
        assert all(line.startswith("- ") for line in row["Expected Result"].splitlines())
        assert "\n" in row["Test Data (exact values)"]


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
    assert "Address: Complete value displayed after Use my current location" in combined
    assert "KTP: 3175070101909999" in combined
    assert "Attachment: New photo captured by the device camera" in combined
    assert "Signature: One continuous handwritten stroke" in combined
    assert "customer card named toko sentosa manual qa" in combined_lower
    assert "card address exactly matches the complete address value" in combined_lower
    assert "card customer type is semi grosir" in combined_lower
    assert "Search or open created customer" not in combined
    assert "customer list/detail" not in combined


def test_manual_company_user_and_handoff_use_the_same_mobile_identity() -> None:
    cases = {row["Test Case ID"]: row for row in _csv_rows()}
    company_user = cases["WEB-TC-006"]
    mobile_login = cases["MOB-TC-001"]
    handoff = cases["E2E-WEB-MOBILE-001"]

    assert "Username: qausermanual" in company_user["Test Data (exact values)"]
    assert "Username: qausermanual" in mobile_login["Test Data (exact values)"]
    assert "Company ID recorded in WEB-TC-004" in mobile_login["Test Data (exact values)"]
    assert "Username: qauserhandoff" in handoff["Test Data (exact values)"]
    assert "No fallback company identity is used" in handoff["Expected Result"]


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
    workbook_rows = _xlsx_rows("Test Cases", width=len(WORKBOOK_HEADERS))
    overview_text = "\n".join(value for row in _xlsx_rows("Overview", width=8) for value in row)

    assert workbook_rows[0] == WORKBOOK_HEADERS
    assert len(workbook_rows) == len(csv_rows) + 1
    assert [row[0] for row in workbook_rows[1:]] == EXPECTED_IDS
    assert workbook_rows[1:] == [[row[header] for header in HEADERS] for row in csv_rows]
    assert "https://github.com/RyanHidayat96/TestEdot" in overview_text


def test_manual_xlsx_has_professional_navigation_and_readable_multiline_rows() -> None:
    with zipfile.ZipFile(XLSX_PATH) as workbook:
        test_cases_member = _xlsx_sheet_member(workbook, "Test Cases")
        overview_member = _xlsx_sheet_member(workbook, "Overview")
        test_cases_xml = workbook.read(test_cases_member).decode("utf-8")
        styles_xml = workbook.read("xl/styles.xml").decode("utf-8")
        overview_relationships = workbook.read(_worksheet_relationships_member(overview_member)).decode(
            "utf-8"
        )
        table_xml = next(
            workbook.read(member).decode("utf-8")
            for member in workbook.namelist()
            if member.startswith("xl/tables/")
            and 'name="ManualTestCases"' in workbook.read(member).decode("utf-8")
        )

    assert 'showGridLines="0"' in test_cases_xml
    assert 'state="frozenSplit"' in test_cases_xml
    assert f'<autoFilter ref="A1:H{len(EXPECTED_IDS) + 1}"' in table_xml
    assert '<dataValidations count="1">' in test_cases_xml
    assert '<rowBreaks count="2" manualBreakCount="2"><brk id="5"' in test_cases_xml
    assert '<brk id="9"' in test_cases_xml
    assert 'paperSize="8"' in test_cases_xml
    assert '<pageSetUpPr fitToPage="1"/>' in test_cases_xml
    assert 'wrapText="1"' in styles_xml
    assert 'Target="https://github.com/RyanHidayat96/TestEdot"' in overview_relationships

    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(test_cases_xml)
    heights = [float(row.attrib["ht"]) for row in root.findall(".//main:sheetData/main:row", namespace)]
    assert max(heights[1:]) >= 300


def test_automated_requirement_flows_are_traceable_to_manual_ids() -> None:
    cases = {
        "tests/web/test_login.py::test_esuite_login_shows_dashboard_greeting": "WEB-TC-001",
        "tests/web/test_create_company.py::test_create_company_three_step_wizard_with_ai_data": "WEB-TC-003",
        "tests/web/test_web_mobile_handoff.py::test_web_created_company_handoff_drives_mobile_login": "E2E-WEB-MOBILE-001",
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


def _xlsx_rows(sheet_name: str, *, width: int) -> list[list[str]]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(XLSX_PATH) as workbook:
        root = ET.fromstring(workbook.read(_xlsx_sheet_member(workbook, sheet_name)))
        shared_strings = _xlsx_shared_strings(workbook)

    rows: list[list[str]] = []
    for row in root.findall(".//main:sheetData/main:row", namespace):
        values = [""] * width
        for cell in row.findall("main:c", namespace):
            match = re.match(r"([A-Z]+)", cell.attrib["r"])
            assert match is not None
            column_index = _column_index(match.group(1))
            if column_index >= width:
                continue
            value_node = cell.find("main:v", namespace)
            if cell.attrib.get("t") == "s" and value_node is not None:
                value = shared_strings[int(value_node.text or 0)]
            elif cell.attrib.get("t") == "inlineStr":
                value = "".join(text.text or "" for text in cell.findall(".//main:t", namespace))
            else:
                value = value_node.text if value_node is not None and value_node.text else ""
            values[column_index] = value
        rows.append(values)
    return rows


def _xlsx_sheet_member(workbook: zipfile.ZipFile, sheet_name: str) -> str:
    main_namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    document_relationship_namespace = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    package_relationship_namespace = "http://schemas.openxmlformats.org/package/2006/relationships"
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships_root.findall(
            f"{{{package_relationship_namespace}}}Relationship"
        )
    }
    sheet = next(
        item
        for item in workbook_root.findall(f".//{{{main_namespace}}}sheet")
        if item.attrib["name"] == sheet_name
    )
    relationship_id = sheet.attrib[f"{{{document_relationship_namespace}}}id"]
    return str(PurePosixPath("xl") / relationship_targets[relationship_id])


def _xlsx_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    member = "xl/sharedStrings.xml"
    if member not in workbook.namelist():
        return []
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(workbook.read(member))
    return [
        "".join(text.text or "" for text in item.findall(".//main:t", namespace))
        for item in root.findall("main:si", namespace)
    ]


def _worksheet_relationships_member(sheet_member: str) -> str:
    sheet_path = PurePosixPath(sheet_member)
    return str(sheet_path.parent / "_rels" / f"{sheet_path.name}.rels")


def _column_index(column_name: str) -> int:
    value = 0
    for character in column_name:
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1
