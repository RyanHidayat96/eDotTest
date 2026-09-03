# eDOT QA Automation Take-Home V4

Clean Python + Pytest automation project for the eDOT QA Automation Engineer V4 assignment.

Repository link: https://github.com/RyanHidayat96/TestEdot

## Scope

- Manual test case workbook: `test_cases/eDOT_QA_Automation_Test_Cases.xlsx`
- Web automation: eSuite at `https://esuite.edot.id` using Playwright, Pytest, Page Object Model, and Allure.
- Mobile automation: eWork SFA using Maestro YAML flows wrapped by Pytest so web and mobile share Allure output.
- AI test data: optional Gemini model call with deterministic Faker fallback.
- AI failure triage: deterministic Allure parser first, optional Gemini note second, Markdown output.

## Project Structure

```text
edot_qa/
  ai/                  AI test-data and failure-triage modules
  mobile/              Maestro runner, ADB checks, mobile config, customer data mapping
  reporting/           Allure attachment helpers
  web/                 eSuite page objects, registration model, storage state helpers
mobile/flows/          Maestro entry flows and reusable runFlow sub-flows
test_cases/            Manual test case CSV and Excel workbook
tests/                 Pytest suites for web, mobile, AI, quality gates
tools/                 Workbook builder and Allure triage CLI
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

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium
npm install
Copy-Item .env.example .env
```

Fill `.env` locally. `.env` is ignored by Git. Do not commit credentials, API keys, storage state, handoff files, Allure results, Maestro output, or generated triage reports.

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
GEMINI_TEST_DATA_MODEL=gemini-2.5-flash-lite
GEMINI_TRIAGE_MODEL=gemini-2.5-flash-lite
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
EWORK_APP_ID=id.edot.ework
EWORK_EMAIL=
EWORK_PASSWORD=
EWORK_COMPANY_NAME=
EWORK_COMPANY_CODE=
EWORK_COMPANY_HANDOFF_PATH=artifacts/handoff/web_company.json
MAESTRO_FLOW_DIR=mobile/flows
MAESTRO_OUTPUT_DIR=artifacts/maestro
EWORK_LOGIN_SCREEN_TEXT=Login
EWORK_COMPANY_ID_FIELD_ID=id.edot.ework:id/tv_company_id
EWORK_USERNAME_FIELD_ID=id.edot.ework:id/tv_username
EWORK_PASSWORD_FIELD_ID=id.edot.ework:id/tv_password
EWORK_LOGIN_BUTTON_ID=id.edot.ework:id/btn_signin
EWORK_DASHBOARD_TEXT=
EWORK_CUSTOMERS_MENU_ID=
EWORK_ADD_CUSTOMER_BUTTON_ID=
EWORK_CUSTOMER_NAME_FIELD_ID=
EWORK_CUSTOMER_CONTACT_FIELD_ID=
EWORK_CUSTOMER_ADDRESS_FIELD_ID=
EWORK_CUSTOMER_SAVE_BUTTON_ID=
EWORK_CUSTOMER_SEARCH_FIELD_ID=
```

Mobile credentials should come from the web-created company handoff where possible. If handoff data is not available, set valid mobile credentials only in local environment variables.
For local live mobile verification in this repository, the assignment-provided fallback eWork account was used because no web-created company handoff was available. The fallback values stay only in the ignored local `.env` file and are not committed.

## Running Tests

You can use the npm shortcuts below from the project root.

```powershell
npm run test:quick
npm run test:ai
npm run test:web:quality
npm run test:web:login
npm run test:web:company:step1
npm run test:web:company:full
npm run test:mobile:foundation
npm run test:mobile:login
npm run test:mobile:customer
```

The full suite shortcut is:

```powershell
npm test
```

The direct Pytest commands are also available when you want to pass extra Pytest options.

All suites:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```

Web suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\web
```

Mobile suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\mobile
```

AI/unit suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ai
```

Quality gates:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\web\test_web_quality_gates.py
```

Tests that require credentials, storage state, Maestro, a device, or the installed mobile app skip with an explicit reason when prerequisites are missing.

## Web Automation

Web tests use Page Object Model classes under `edot_qa/web/pages`. Test files do not own raw Playwright selectors. Login creates or reuses `PLAYWRIGHT_STORAGE_STATE` so authenticated tests do not log in repeatedly.

Implemented web behaviors:

- Login through eDOT Account Center and assert dashboard greeting `Welcome Back,`.
- Register company through the 3-step wizard.
- Verify company detail values field by field as Tier 2 assertions.
- Attempt cleanup after company creation and assert the record is gone without hiding the original failure.

## Mobile Automation

Check local runtime first:

```powershell
maestro --version
adb devices
```

The eWork SFA app package is `id.edot.ework`. Current login selectors were confirmed from Android UI hierarchy: `tv_company_id`, `tv_username`, `tv_password`, and `btn_signin`. Use Maestro Studio or hierarchy inspection to discover dashboard/customer selectors, then place them in `.env`. Flows live in `mobile/flows`. Reused login is in `mobile/flows/common/login.yaml` and is called with `runFlow`.

Implemented mobile behaviors:

- Login flow launches eWork SFA, runs the shared login sub-flow, and asserts dashboard text.
- Customer creation flow runs login, creates a customer from AI-generated or fallback data, then asserts the saved name, contact, and address as Tier 2 checks.
- Maestro stdout, stderr, command details, and supported output artifacts are attached to Allure.

## Web-to-Mobile Handoff

When a web company is created, `edot_qa.handoff` can write non-secret runtime company data to `artifacts/handoff/web_company.json`. Mobile config reads this file for company name/email when explicit mobile environment values are absent. Passwords are never written to handoff files.

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

## AI Failure Triage

Create a deterministic triage report from Allure results:

```powershell
.\.venv\Scripts\python.exe tools\triage_allure_failures.py --results-dir reports\allure-results --output reports\triage\triage-report.md --no-ai
```

Use optional AI notes when `GEMINI_API_KEY` is set:

```powershell
.\.venv\Scripts\python.exe tools\triage_allure_failures.py --results-dir reports\allure-results --output reports\triage\triage-report.md
```

Triage verdicts are human-review proposals only. The script never changes tests, weakens assertions, edits expected values, files bugs, or closes bugs.

## Troubleshooting

- Missing `ESUITE_EMAIL` or `ESUITE_PASSWORD`: live web login and authenticated web tests skip unless storage state already exists.
- Stale storage state: remove `artifacts/auth/esuite_storage_state.json` and rerun web tests with valid credentials.
- Missing Maestro CLI: mobile live tests skip until `maestro --version` works.
- No ready device: check `adb devices`; set `MOBILE_DEVICE_ID` when more than one device is attached.
- eWork app not installed or wrong app ID: set `EWORK_APP_ID` from the installed package name.
- Missing mobile selectors: discover stable IDs through Maestro and set the `EWORK_*_ID` variables.
- Missing `GEMINI_API_KEY`: AI test data uses deterministic Faker fallback; triage still produces deterministic verdicts.

## Current Local Verification Notes

Local unit and guardrail tests pass without committed secrets. Live mobile login has been verified on a physical ADB device using the assignment-provided fallback eWork account. Live mobile customer creation still requires post-login customer selectors. Live web execution still depends on valid eSuite credentials or storage state.
