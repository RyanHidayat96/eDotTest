from __future__ import annotations

import csv
import datetime as dt
import html
import pathlib
import zipfile
from typing import Iterable


ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "test_cases" / "manual_test_cases.csv"
OUTPUT_PATH = ROOT / "test_cases" / "eDOT_QA_Automation_Test_Cases.xlsx"


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


METADATA_ROWS = [
    ["Field", "Value"],
    ["Source of truth", "Take Home Test QA Automation Engineer eDOT V4.pdf"],
    ["Execution framework", "edot_codex_qa_automation_plan.md"],
    ["Repository link", "https://github.com/RyanHidayat96/TestEdot"],
    ["Credential policy", "Use environment variables only; no credentials or API keys stored in workbook"],
    ["Runtime data token", "${RUN_ID} is replaced by suite-generated unique run id"],
    ["Negative assertion note", "No invented product error copy. Later negative submit tests must assert exact app error text discovered from product."],
]


def col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def cell_ref(row_index: int, col_index: int) -> str:
    return f"{col_name(col_index)}{row_index}"


def inline_cell(row_index: int, col_index: int, value: str, style: int = 0) -> str:
    escaped = html.escape(value, quote=False)
    style_attr = f' s="{style}"' if style else ""
    return (
        f'<c r="{cell_ref(row_index, col_index)}" t="inlineStr"{style_attr}>'
        f"<is><t>{escaped}</t></is></c>"
    )


def row_xml(row_index: int, row: Iterable[str], style: int = 0, height: int | None = None) -> str:
    height_attr = f' ht="{height}" customHeight="1"' if height else ""
    cells = "".join(inline_cell(row_index, col_index, str(value), style) for col_index, value in enumerate(row, 1))
    return f'<row r="{row_index}"{height_attr}>{cells}</row>'


def columns_xml(widths: list[float]) -> str:
    columns = []
    for index, width in enumerate(widths, 1):
        columns.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
    return f"<cols>{''.join(columns)}</cols>"


def worksheet_xml(rows: list[list[str]], widths: list[float], freeze_top_row: bool = True, status_validation: bool = False) -> str:
    max_col = len(rows[0])
    max_row = len(rows)
    dimension = f"A1:{cell_ref(max_row, max_col)}"
    sheet_views = (
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A2" sqref="A2"/>'
        "</sheetView></sheetViews>"
        if freeze_top_row
        else '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
    )
    body_rows = []
    for index, row in enumerate(rows, 1):
        if index == 1:
            body_rows.append(row_xml(index, row, style=1, height=24))
        else:
            body_rows.append(row_xml(index, row, style=2, height=72 if max_col == 8 else 28))
    validations = ""
    if status_validation:
        validations = (
            '<dataValidations count="1"><dataValidation type="list" allowBlank="1" '
            'showErrorMessage="1" sqref="H2:H200"><formula1>"Not Run,Passed,Failed,Blocked"</formula1>'
            "</dataValidation></dataValidations>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        f"{sheet_views}"
        f"{columns_xml(widths)}"
        f"<sheetData>{''.join(body_rows)}</sheetData>"
        f"{validations}"
        "</worksheet>"
    )


def read_test_cases() -> list[list[str]]:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows or rows[0] != HEADERS:
        raise ValueError("CSV headers do not match assignment-required columns exactly")
    if len(rows) < 6:
        raise ValueError("Manual test case coverage is incomplete")
    return rows


def write_workbook(test_case_rows: list[list[str]]) -> None:
    test_case_widths = [16, 34, 44, 58, 66, 48, 16, 14]
    metadata_widths = [26, 82]
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Test Cases" sheetId="1" r:id="rId1"/>
    <sheet name="Metadata" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="10"/><name val="Calibri"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFD9E2EC"/></left><right style="thin"><color rgb="FFD9E2EC"/></right><top style="thin"><color rgb="FFD9E2EC"/></top><bottom style="thin"><color rgb="FFD9E2EC"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>""",
        "xl/worksheets/sheet1.xml": worksheet_xml(test_case_rows, test_case_widths, status_validation=True),
        "xl/worksheets/sheet2.xml": worksheet_xml(METADATA_ROWS, metadata_widths),
        "docProps/app.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Python workbook builder</Application>
</Properties>""",
        "docProps/core.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>eDOT QA Automation Manual Test Cases</dc:title>
  <dc:creator>Ryan Hidayat</dc:creator>
  <cp:lastModifiedBy>Ryan Hidayat</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z</dcterms:modified>
</cp:coreProperties>""",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT_PATH, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        for name, content in files.items():
            workbook.writestr(name, content)


if __name__ == "__main__":
    write_workbook(read_test_cases())
    print(OUTPUT_PATH)
