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
  mobile/              Mobile config, scenario orchestration, Maestro runner, ADB/device helpers
    scenarios/         Thin business flows for login and customer creation
    customer_list.py   Customer-list card parsing and Tier 2 validation helpers
    runtime.py         Mobile prerequisite checks and app-session actions
  reporting/           Allure attachment, metadata, and category helpers
  web/                 eSuite page objects, registration model, scenarios, storage state helpers
    scenarios/         Thin business flows for login and company registration
mobile/flows/          Maestro entry flows and reusable runFlow sub-flows
test_cases/            Final manual test case workbook
tests/                 Pytest suites for web, mobile, AI, quality gates
tools/                 Safety checker, Allure report generator, and triage CLI
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

`.env` is reserved for secrets, machine-specific tools/device selection, and target runtime values. Static test data, repository paths, and app selectors are source-controlled instead of being hidden deployment configuration.

```text
# eSuite web
ESUITE_BASE_URL=https://esuite.edot.id
ESUITE_EMAIL=
ESUITE_PASSWORD=
HEADLESS=true
SLOW_MO_MS=0
BROWSER=chromium

# Local evidence policy
ALLURE_SHOW_DEV_INPUTS=false

# Optional Gemini-backed test data
GEMINI_API_KEY=
GEMINI_TEST_DATA_MODEL=gemini-3.1-flash-lite

# Local Android / Maestro runtime
MAESTRO_CLI=maestro
ADB_COMMAND=adb
MOBILE_DEVICE_ID=
MOBILE_FLOW_TIMEOUT_SECONDS=300
EDOT_LIVE=false
EWORK_APP_ID=id.edot.ework
EWORK_EMAIL=
EWORK_PASSWORD=
EWORK_COMPANY_CODE=
```

`ALLURE_SHOW_DEV_INPUTS=false` is the safe default. Set it to `true` only for a local development report when visible credential input evidence is intentional.

The eSuite company-registration defaults live in `edot_qa/web/company_registration.py`; eWork locator IDs, fixed labels, and selected options live in `edot_qa/mobile/flow_profile.py`; runtime artifact paths live in their owning config modules. Change those values through reviewed source changes, not `.env` edits.

Mobile credentials normally come from explicit local `.env` values. The dedicated `test:handoff` path requests web-to-mobile handoff directly in code, creates a Company User with a generated runtime password, and uses that identity only for its matching eWork login.

## Web Execution

You can use the npm shortcuts below from the project root.

```powershell
npm run test:web
npm run test:web:login
npm run test:web:company
```

`test:web:login` always performs credential input and creates a fresh storage-state file at `artifacts/auth/esuite_storage_state.json` after successful login. Authenticated business tests reuse that state so they do not repeat login unless it is missing or stale.

Web behavior covered:

- Login through eDOT Account Center and assert dashboard greeting `Welcome Back,`.
- Register company through the 3-step wizard using AI-generated or fallback dummy data.
- Verify company detail values field by field as Tier 2 assertions.
- Delete the created company and assert the company name and captured Company ID are gone from Companies results.

Direct Pytest form:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\web -m "not deliberate_failure"
```

Portable form:

```bash
python -m pytest tests/web -m "not deliberate_failure"
```

## Mobile Execution

Check local runtime first:

```powershell
maestro --version
adb devices
```

The eWork SFA app package is `id.edot.ework`. Current login selectors were confirmed from Android UI hierarchy: `tv_company_id`, `tv_username`, `tv_password`, and `btn_signin`. Dashboard text `Revenue` and the customer path through `New Customer`, `New Customer Registration`, Basic fields, channel/type dropdowns, location dropdowns, KTP document upload, signature, register, confirmation, and success screen were captured from the real app. The Home menu uses shared menu containers, so `New Customer` is opened through parent id `home_container_menu` plus exact child text to avoid tapping nearby menu items. The New Customer List screen did not expose a search input in hierarchy, and cards do not open a detail page, so the flow checks the current list view first, then fast-scrolls to the bottom, then searches upward at most four slow swipes while validating the saved name, current-location address, and customer type exposed by the card. Flows live in `mobile/flows`. Reused login is in `mobile/flows/common/login.yaml` and is called with `runFlow`.

Run mobile checks:

```powershell
npm run test:mobile
npm run test:mobile:login
npm run test:mobile:customer
```

`test:mobile:login` clears app data, inputs company code, username, and password, then writes a non-secret session marker at `artifacts/auth/ework_session_state.json`. `test:mobile:customer` consumes the existing app session on the device, so it does not clear app data or input credentials.

Direct Pytest form:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\mobile -m "not deliberate_failure" -q -rs
```

Portable form:

```bash
python -m pytest tests/mobile -m "not deliberate_failure" -q -rs
```

Ordinary developer mobile runs skip external checks with an explicit reason when prerequisites are missing. Set `EDOT_LIVE=true` for a declared live/submission run; missing mobile selectors, Maestro, ADB, device, app, or credentials then fail the mandatory scenario instead of producing a misleading green skip.

Implemented mobile behaviors:

- Login flow launches eWork SFA, runs the shared login sub-flow, and asserts dashboard text.
- Customer creation flow consumes AI-generated or fallback customer name/contact/address data. The real eWork form resolves the saved address from `Use my current location`, so the generated address is recorded as generated context while the captured current-location address is used for persisted card validation.
- Maestro stdout, stderr, command details, and supported output artifacts are attached to Allure.

For local live mobile verification in this repository, the assignment-provided fallback eWork account was used because no web-created company handoff was available. The fallback password is not stored in this README and must stay only in ignored local environment configuration.

## AI Checks

```powershell
npm run test:ai
```

Direct Pytest forms:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -m "not deliberate_failure"
.\.venv\Scripts\python.exe -m pytest tests\ai
```

## Web-to-Mobile Handoff

When a web company is created, `edot_qa.handoff` can write non-secret runtime company data to `artifacts/handoff/web_company.json`, including company name, company email, captured Company ID/code, and the web-created Company User username. Normal mobile runs do not consume this file. The dedicated handoff proof explicitly requests it, creates a Company User under Manage > Company User > Add User, then logs in to eWork with that username and the same generated runtime password used when creating that user. Passwords are never written to handoff files.

Run the dedicated live handoff proof:

```powershell
npm run test:handoff
```

## Bonus Features

Implemented bonus scope:

- Genuine web-to-mobile handoff: `npm run test:handoff` creates a company through eSuite web, verifies Tier 2 web detail, creates a Company User for that company, writes only non-secret handoff data, then attempts eWork login using that created Company User identity. Treat this bonus as proven only when the live run passes.

## Allure Reporting

Pytest writes Allure results to `reports/allure-results` by default:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -m "not deliberate_failure" --alluredir reports/allure-results
```

Results are cumulative across different test commands. When the same test is rerun, `npm run allure:generate` keeps only the latest result for that test identity in the HTML report, so `test:web:login` followed by `test:web:company` shows both, while rerunning `test:web:login` replaces its previous run.

`ALLURE_SHOW_DEV_INPUTS=false` keeps generated evidence secret-safe. Set it to `true` only for a local development report that intentionally shows login inputs.

Generate and open the shared web/mobile HTML report through the repository-local Allure CLI:

```powershell
npm run allure:generate
```

The Allure binary comes from `allure-commandline` in `devDependencies`, same as a local Node-based automation project. No global Allure PATH is required.

Generated Allure reports include eDOT-specific suite hierarchy, Behaviors labels, owner, severity, test case IDs for live requirement flows, environment properties, executor metadata, defect categories, and preserved trend history from the previous report. Reports are intentionally lean: page-level web steps show one input summary only when fields are entered, login input evidence is visible for the local dev report when `ALLURE_SHOW_DEV_INPUTS=true`, successful UI screenshots are captured at page-open/page-change milestones such as login, wizard pages, submit success, manage/detail pages, and mobile list validation, failures attach full-page evidence, and Maestro steps attach input summaries, redacted commands/logs, flow YAML, result JSON, device screenshots, and supported output artifacts.

If `reports/triage/triage-report.md` exists, `npm run allure:generate` attaches it into the same shared Allure report as an Evidence item. Deliberate wrong-locator evidence stays failed in Allure by design so triage can read the real failure status, stack trace, screenshots, and Maestro output.

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

## Deliberate Failure Evidence

```powershell
npm run test:web:deliberate
npm run test:mobile:deliberate
npm run triage
npm run allure:generate
```

Web opens the eSuite login page and points the login button assertion at a wrong locator. Mobile opens the eWork login flow and points the password field at a wrong id. These deliberate tests stay failed under `eDOT Evidence` by design, then `npm run triage` reads those failures and `npm run allure:generate` shows the triage report in the shared Allure report.

## Test Data Cleanup

Web company tests create unique company names per run. The full company flow deletes only the company it created, then verifies both the company name and captured Company ID are absent from Companies results. If eSuite still shows the deleted company after confirmation, the cleanup assertion remains failed so the shared-environment data issue is visible.

Mobile customer tests use AI-generated or deterministic fallback customer data. eWork currently stores the customer address from current-location resolution, so Allure distinguishes generated customer address from the persisted address captured from the app.

## Evidence

Final evidence is generated in the dedicated final execution step. Expected evidence locations are:

```text
evidence/README.md
reports/allure-results/
reports/allure-report/
reports/triage/triage-report.md
```

Generated evidence folders are ignored by Git. Run `python tools/check_submission_safety.py` before any submission archive is created.

## Troubleshooting

- Missing `ESUITE_EMAIL` or `ESUITE_PASSWORD`: live web login and authenticated web tests skip unless storage state already exists.
- Stale storage state: remove `artifacts/auth/esuite_storage_state.json` and rerun web tests with valid credentials.
- Missing Maestro CLI: mobile live tests skip until `maestro --version` works.
- No ready device: check `adb devices`; set `MOBILE_DEVICE_ID` when more than one device is attached.
- eWork app not installed or wrong app ID: set `EWORK_APP_ID` from the installed package name.
- Missing mobile selectors: capture stable IDs through Maestro, then update the reviewed eWork profile in `edot_qa/mobile/flow_profile.py` together with its consuming flow.
- Missing `GEMINI_API_KEY`: AI test data uses deterministic Faker fallback; triage still produces deterministic verdicts.

## Known Environment Constraints

- Windows mobile execution usually needs Maestro through WSL, while `adb` must still see the target Android device.
- Live web tests need valid eSuite credentials or a valid storage state.
- Live mobile tests need eWork SFA installed, an ADB-visible device, valid mobile credentials, and configured dashboard/customer selectors. Use `EDOT_LIVE=true` for submission evidence so missing mobile prerequisites fail visibly.
- The full web company flow can fail cleanup when eSuite continues showing a deleted company in Companies results after confirmation. That assertion is intentionally preserved as an application-visible defect, not hidden.
