# eDOT QA Automation Take-Home V4

Clean Python + Pytest automation project for the eDOT QA Automation Engineer V4 assignment.

Repository link: https://github.com/RyanHidayat96/TestEdot

## Scope

- Manual test case workbook: `test_cases/eDOT_QA_Automation_Test_Cases.xlsx`
- Web automation: eSuite at `https://esuite.edot.id` using Playwright, Pytest, Page Object Model, and Allure.
- Mobile automation: eWork SFA using Maestro YAML flows wrapped by Pytest so web and mobile share Allure output.
- AI test data: optional Gemini model call with deterministic Faker fallback.
- AI failure triage: deterministic Allure parser first, optional schema-constrained Gemini proposal second, Markdown output.

## Project Structure

```text
edot_qa/
  ai/                  AI test-data and failure-triage modules
  mobile/              Maestro runner, ADB checks, mobile config, customer data mapping
  reporting/           Allure attachment, metadata, and category helpers
  web/                 eSuite page objects, registration model, storage state helpers
mobile/flows/          Maestro entry flows and reusable runFlow sub-flows
test_cases/            Manual test case CSV and Excel workbook
tests/                 Pytest suites for web, mobile, AI, quality gates
tools/                 Safety checker, workbook builder, Allure report generator, and triage CLI
```

## Prerequisites

- Python 3.11 or newer.
- Node.js and npm for the local Allure commandline dependency.
- Playwright browsers.
- Java for Allure report generation.
- Android platform-tools with `adb` on `PATH`.
- Maestro CLI on `PATH`. On Windows, Maestro is normally run through WSL.
- Android emulator or physical device visible in `adb devices`.
- eWork SFA installed on that device for live mobile tests.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium
npm install
Copy-Item .env.example .env
```

Portable form for macOS, Linux, or WSL:

```bash
python -m venv .venv
python -m pip install -e .
python -m playwright install chromium
npm install
cp .env.example .env
```

Fill `.env` locally. `.env` is ignored by Git. Never commit `.env`, credentials, API keys, storage state, handoff files, Allure results, Maestro output, or generated triage reports.

Before packaging or pushing, run:

```bash
python tools/check_submission_safety.py
```

Create a safe submission archive from committed files only:

```bash
git archive --format=zip --output edot-qa-automation-submission.zip HEAD
```

## Environment Variables

Core web values:

```text
ESUITE_BASE_URL=https://esuite.edot.id
ESUITE_EMAIL=
ESUITE_PASSWORD=
HEADLESS=true
BROWSER=chromium
PLAYWRIGHT_STORAGE_STATE=artifacts/auth/esuite_storage_state.json
ALLURE_RESULTS_DIR=reports/allure-results
```

Company registration defaults:

```text
ESUITE_COMPANY_TYPE=Retailer
ESUITE_COMPANY_LANGUAGE=English
ESUITE_COMPANY_COUNTRY=Indonesia
ESUITE_COMPANY_PROVINCE=DKI Jakarta
ESUITE_COMPANY_CITY=Jakarta Selatan
ESUITE_COMPANY_DISTRICT=Kebayoran Baru
ESUITE_COMPANY_ZONE=Senayan
ESUITE_COMPANY_POSTAL_CODE=12190
```

AI values:

```text
GEMINI_API_KEY=
GEMINI_TEST_DATA_MODEL=gemini-3.1-flash-lite
GEMINI_TRIAGE_MODEL=gemini-3.1-flash-lite
AI_TEST_DATA_MAX_ATTEMPTS=2
AI_TEST_DATA_MAX_OUTPUT_TOKENS=700
AI_TRIAGE_MAX_OUTPUT_TOKENS=900
TRIAGE_REPORT_PATH=reports/triage/triage-report.md
```

Mobile values:

```text
MAESTRO_CLI=maestro
ADB_COMMAND=adb
MOBILE_DEVICE_ID=
MOBILE_FLOW_TIMEOUT_SECONDS=300
EDOT_LIVE=false
EWORK_APP_ID=id.edot.ework
EWORK_EMAIL=
EWORK_PASSWORD=
EWORK_COMPANY_NAME=
EWORK_COMPANY_CODE=
EWORK_PREFER_HANDOFF=false
EWORK_COMPANY_HANDOFF_PATH=artifacts/handoff/web_company.json
EWORK_STORAGE_STATE=artifacts/auth/ework_session_state.json
MAESTRO_FLOW_DIR=mobile/flows
MAESTRO_OUTPUT_DIR=artifacts/maestro
EWORK_LOGIN_SCREEN_TEXT=Login
EWORK_COMPANY_ID_FIELD_ID=id.edot.ework:id/tv_company_id
EWORK_USERNAME_FIELD_ID=id.edot.ework:id/tv_username
EWORK_PASSWORD_FIELD_ID=id.edot.ework:id/tv_password
EWORK_LOGIN_BUTTON_ID=id.edot.ework:id/btn_signin
EWORK_DASHBOARD_TEXT=Revenue
EWORK_CUSTOMERS_MENU_ID=id.edot.ework:id/home_container_menu
EWORK_CUSTOMERS_MENU_TEXT=^New Customer$
EWORK_ADD_CUSTOMER_BUTTON_ID=id.edot.ework:id/noo_label_add_new_cust
EWORK_CUSTOMER_NAME_FIELD_ID=id.edot.ework:id/noo_registration_input_outlet_name
EWORK_CUSTOMER_CONTACT_FIELD_ID=id.edot.ework:id/noo_registration_input_phone
EWORK_CUSTOMER_CONTACT_PERSON_FIELD_ID=id.edot.ework:id/noo_registration_input_contact_person
EWORK_CUSTOMER_CHANNEL_FIELD_ID=id.edot.ework:id/noo_registration_input_channel
EWORK_CUSTOMER_CHANNEL_OPTION_TEXT=Modern Trade (MT)
EWORK_CUSTOMER_TYPE_FIELD_ID=id.edot.ework:id/noo_registration_input_outlet_type
EWORK_CUSTOMER_TYPE_OPTION_TEXT=Semi Grosir
EWORK_CUSTOMER_BASIC_CONTINUE_BUTTON_ID=id.edot.ework:id/noo_registration_action_submit
EWORK_CUSTOMER_ADDRESS_TYPE_FIELD_ID=id.edot.ework:id/noo_registration_input_address_type
EWORK_CUSTOMER_ADDRESS_TYPE_OPTION_TEXT=Delivery Address
EWORK_CUSTOMER_CURRENT_LOCATION_BUTTON_ID=id.edot.ework:id/noo_registration_container_use_my_current_location
EWORK_CUSTOMER_PROVINCE_FIELD_TEXT=Choose Province
EWORK_CUSTOMER_PROVINCE_OPTION_TEXT=DKI JAKARTA
EWORK_CUSTOMER_CITY_FIELD_TEXT=Choose City
EWORK_CUSTOMER_CITY_OPTION_TEXT=JAKARTA BARAT
EWORK_CUSTOMER_DISTRICT_FIELD_TEXT=Choose District
EWORK_CUSTOMER_DISTRICT_OPTION_TEXT=KEBON JERUK
EWORK_CUSTOMER_SUBDISTRICT_FIELD_TEXT=Choose Sub district
EWORK_CUSTOMER_SUBDISTRICT_OPTION_TEXT=KEBON JERUK
EWORK_CUSTOMER_POSTAL_CODE_FIELD_TEXT=Choose Postal code
EWORK_CUSTOMER_POSTAL_CODE_OPTION_TEXT=11530
EWORK_CUSTOMER_ADDRESS_FIELD_ID=id.edot.ework:id/noo_registration_input_address
EWORK_CUSTOMER_KTP_FIELD_ID=id.edot.ework:id/update_info_item_input_value
EWORK_CUSTOMER_UPLOAD_BUTTON_ID=id.edot.ework:id/btn_upload
EWORK_CUSTOMER_CAMERA_CAPTURE_BUTTON_ID=id.edot.ework:id/btn_capture
EWORK_CUSTOMER_DOCUMENT_SUBMIT_BUTTON_ID=id.edot.ework:id/noo_registration_doc_action_continue
EWORK_CUSTOMER_SIGNATURE_TITLE_TEXT=Approval Signature
EWORK_CUSTOMER_SIGNATURE_VIEW_ID=id.edot.ework:id/signature_view
EWORK_CUSTOMER_SAVE_BUTTON_ID=id.edot.ework:id/update_info_action_submit
EWORK_CUSTOMER_SAVE_CONFIRM_BUTTON_ID=id.edot.ework:id/btn_positive
EWORK_CUSTOMER_SUCCESS_TEXT=Data Saved Successfully
EWORK_CUSTOMER_SUCCESS_CONTINUE_BUTTON_ID=id.edot.ework:id/btn_success_continue
EWORK_CUSTOMER_SEARCH_FIELD_ID=
```

Mobile credentials should come from the web-created company handoff only when the product has proven that the created company can log in to eWork. Default mobile runs keep explicit `.env` fallback identity first. Set `EWORK_PREFER_HANDOFF=true` only for the dedicated handoff proof; the password still comes from secure local environment variables.

## Web Execution

You can use the npm shortcuts below from the project root.

```powershell
npm run test:web:quality
npm run test:web:login
npm run test:web:company:step1
npm run test:web:company:full
```

`test:web:login` always performs credential input and creates a fresh `PLAYWRIGHT_STORAGE_STATE` after successful login. Authenticated business tests reuse that storage state so they do not repeat login unless the state is missing or stale.

Web behavior covered:

- Login through eDOT Account Center and assert dashboard greeting `Welcome Back,`.
- Validate Register Company step 1 required fields and location cascade.
- Register company through the 3-step wizard using AI-generated or fallback dummy data.
- Verify company detail values field by field as Tier 2 assertions.
- Delete the created company and assert the company name and captured Company ID are gone from Companies results.

Direct Pytest form:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\web
```

Portable form:

```bash
python -m pytest tests/web
```

## Mobile Execution

Check local runtime first:

```powershell
maestro --version
adb devices
```

The eWork SFA app package is `id.edot.ework`. Current login selectors were confirmed from Android UI hierarchy: `tv_company_id`, `tv_username`, `tv_password`, and `btn_signin`. Dashboard text `Revenue` and the customer path through `New Customer`, `New Customer Registration`, Basic fields, channel/type dropdowns, location dropdowns, KTP document upload, signature, register, confirmation, and success screen were captured from the real app. The Home menu uses shared menu containers, so `New Customer` is opened through parent id `home_container_menu` plus exact child text to avoid tapping nearby menu items. The New Customer List screen did not expose a search input in hierarchy, and cards do not open a detail page, so the flow checks the current list view first, then fast-scrolls to the bottom, then searches upward at most four slow swipes while validating the saved name, address, and customer type exposed by the card. Flows live in `mobile/flows`. Reused login is in `mobile/flows/common/login.yaml` and is called with `runFlow`.

Run mobile checks:

```powershell
npm run test:mobile:foundation
npm run test:mobile:login
npm run test:mobile:customer
```

`test:mobile:login` clears app data, inputs company code, username, and password, then writes a non-secret `EWORK_STORAGE_STATE` marker. `test:mobile:customer` consumes the existing app session on the device, so it does not clear app data and does not input credentials.

Direct Pytest form:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\mobile -q -rs
```

Portable form:

```bash
python -m pytest tests/mobile -q -rs
```

Ordinary developer mobile runs skip external checks with an explicit reason when prerequisites are missing. Set `EDOT_LIVE=true` for a declared live/submission run; missing mobile selectors, Maestro, ADB, device, app, or credentials then fail the mandatory scenario instead of producing a misleading green skip.

Implemented mobile behaviors:

- Login flow launches eWork SFA, runs the shared login sub-flow, and asserts dashboard text.
- Customer creation flow runs login, creates a customer from AI-generated or fallback data, jumps to the bottom of the customer list, and asserts the saved name, address, and customer type currently exposed by the card.
- Maestro stdout, stderr, command details, and supported output artifacts are attached to Allure.

For local live mobile verification in this repository, the assignment-provided fallback eWork account was used because no web-created company handoff was available. The fallback password is not stored in this README and must stay only in ignored local environment configuration.

## Other Test Commands

```powershell
npm run test:quick
npm run test:ai
npm test
```

Direct Pytest forms:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m pytest tests\ai
.\.venv\Scripts\python.exe -m pytest tests\web\test_web_quality_gates.py
```

## Web-to-Mobile Handoff

When a web company is created, `edot_qa.handoff` can write non-secret runtime company data to `artifacts/handoff/web_company.json`, including company name, company email, and captured Company ID/code. Mobile config normally reads this only when explicit mobile environment values are absent. In the dedicated handoff proof, `EWORK_PREFER_HANDOFF=true` makes handoff company identity override fallback identity. Passwords are never written to handoff files, and company email is not assumed to be a valid mobile username unless the live mobile login succeeds with it.

## Allure Reporting

Pytest writes Allure results to `reports/allure-results` by default:

```powershell
.\.venv\Scripts\python.exe -m pytest tests --alluredir reports/allure-results
```

Generate and open the HTML report through the repository-local Allure CLI:

```powershell
npm run allure:generate
npm run allure:open
```

Generate the latest mobile live report:

```powershell
npm run allure:generate:mobile
npm run allure:open:mobile
```

The Allure binary comes from `allure-commandline` in `devDependencies`, same as a local Node-based automation project. No global Allure PATH is required.

Generated Allure reports include eDOT-specific suite hierarchy, Behaviors labels, owner, severity, test case IDs for live requirement flows, environment properties, executor metadata, defect categories, and preserved trend history from the previous report. Reports are intentionally lean: page-level web steps show one redacted input summary only when fields are entered, successful UI screenshots are captured at important milestones such as submit success, failures attach full-page evidence, and Maestro steps attach redacted commands, flow YAML, stdout/stderr, result JSON, device screenshots, and supported output artifacts.

## AI Failure Triage

Create a deterministic triage report from Allure results:

```powershell
.\.venv\Scripts\python.exe tools\triage_allure_failures.py --results-dir reports\allure-results --output reports\triage\triage-report.md --no-ai
```

Use optional AI notes when `GEMINI_API_KEY` is set:

```powershell
.\.venv\Scripts\python.exe tools\triage_allure_failures.py --results-dir reports\allure-results --output reports\triage\triage-report.md
```

Pass prior safe result history when checking flaky evidence across cleaned runs:

```powershell
.\.venv\Scripts\python.exe tools\triage_allure_failures.py --results-dir reports\allure-results --history-dir reports\allure-history --output reports\triage\triage-report.md
```

Triage verdicts are human-review proposals only. The script never changes tests, weakens assertions, edits expected values, files bugs, or closes bugs.

## Evidence Commands

Dry-run evidence commands first:

```powershell
npm run evidence:web:dry-run
npm run evidence:deliberate:dry-run
npm run evidence:validate
```

Final web evidence command:

```powershell
npm run evidence:web
```

This cleans `reports/allure-results` and `evidence/web-allure`, runs the required web login/company scenarios, generates the preserved Allure HTML report in `evidence/web-allure`, then scans preserved evidence for secrets.

Deliberate-failure evidence command:

```powershell
npm run evidence:deliberate
```

This runs only the isolated wrong-locator evidence test with `EDOT_DELIBERATE_FAILURE=wrong_locator`, expects that test to fail, writes triage to `evidence/triage/triage-report.md`, generates `evidence/deliberate-allure`, then scans preserved evidence for secrets. Normal suites do not enable this flag.

Manual evidence safety scan:

```powershell
npm run evidence:scan
```

## Test Data Cleanup

Web company tests create unique company names per run. The full company flow deletes only the company it created, then verifies both the company name and captured Company ID are absent from Companies results. If eSuite still shows the deleted company after confirmation, the cleanup assertion remains failed so the shared-environment data issue is visible.

Mobile customer tests use AI-generated or deterministic fallback customer data. The mandatory customer scenario should be run only after real customer selectors are configured so created data can be tied back to the exact saved record.

## Evidence

Final evidence is generated in the dedicated final execution step. Expected evidence locations are:

```text
evidence/README.md
evidence/web-allure/
evidence/deliberate-allure/
evidence/triage/triage-report.md
reports/allure-results/
reports/allure-results-deliberate/
```

Generated evidence folders are ignored by Git and must be scanned with `npm run evidence:scan` plus `python tools/check_submission_safety.py` before any submission archive is created.

## Troubleshooting

- Missing `ESUITE_EMAIL` or `ESUITE_PASSWORD`: live web login and authenticated web tests skip unless storage state already exists.
- Stale storage state: remove `artifacts/auth/esuite_storage_state.json` and rerun web tests with valid credentials.
- Missing Maestro CLI: mobile live tests skip until `maestro --version` works.
- No ready device: check `adb devices`; set `MOBILE_DEVICE_ID` when more than one device is attached.
- eWork app not installed or wrong app ID: set `EWORK_APP_ID` from the installed package name.
- Missing mobile selectors: discover stable IDs through Maestro and set the `EWORK_*_ID` variables.
- Missing `GEMINI_API_KEY`: AI test data uses deterministic Faker fallback; triage still produces deterministic verdicts.

## Known Environment Constraints

- Windows mobile execution usually needs Maestro through WSL, while `adb` must still see the target Android device.
- Live web tests need valid eSuite credentials or a valid storage state.
- Live mobile tests need eWork SFA installed, an ADB-visible device, valid mobile credentials, and configured dashboard/customer selectors. Use `EDOT_LIVE=true` for submission evidence so missing mobile prerequisites fail visibly.
- The full web company flow can fail cleanup when eSuite continues showing a deleted company in Companies results after confirmation. That assertion is intentionally preserved as an application-visible defect, not hidden.
