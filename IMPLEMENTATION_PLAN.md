# eDOT QA Automation Implementation Plan

Source of truth: `Take Home Test QA Automation Engineer eDOT V4.pdf`.
Execution framework: `edot_codex_qa_automation_plan.md`.

## Step 0 Reconnaissance Summary

- Repository currently contains only the assignment PDF, the Codex execution plan, and this implementation plan.
- No Git repository is initialized in this folder, so `git status` is unavailable here.
- No automation code, test cases, README, AI documentation, CI, environment example, or Allure output exists yet.
- Runtime check: Python 3.11.0, Node 22.19.0, npm 10.9.3, Git 2.50.0, Java 21, and ADB 37.0.1 are available.
- Missing or not on PATH: `pytest`, Allure CLI, Maestro CLI, Poppler PDF tools.
- Python package check: `playwright`, `pydantic`, and `yaml` are available; `pytest`, `allure_commons`, `faker`, and `openpyxl` are missing.

## Requirements Checklist

### Phase 1 - Manual Test Case Design

- [ ] Excel or Google-Sheet-ready manual test case document.
- [ ] Required columns exactly: `Test Case ID | Title / Description | Precondition | Test Steps | Test Data (exact values) | Expected Result | Assertion Tier | Status`.
- [ ] Web scenarios: login, create new company, verify created company data in detail view.
- [ ] Mobile scenarios: login with newly created company credentials, create customer.
- [ ] Tier 1, Tier 2, delete, edit, and negative assertion rules represented correctly.
- [ ] Tier 2 automation assertions later marked with short code comments.
- [ ] GitHub repository link included in the sheet when a repo exists.

### Phase 2A - Web Automation

- [ ] Python + Pytest + Playwright + Allure.
- [ ] Page Object Model.
- [ ] Target `https://esuite.edot.id`.
- [ ] Credentials from environment variables only.
- [ ] Login flow covers `Use Email or Username`, email screen, password screen, eDOT Account Center redirect, and return.
- [ ] Dashboard assertion checks `Welcome Back,`.
- [ ] Create company covers `Companies` to `+ Add Company` and the 3-step Register Company wizard.
- [ ] Step 1 covers company name, email, phone, industry type, company type, language, street address, and dependent location cascade.
- [ ] Assert `Next` stays disabled until step is valid.
- [ ] Company test data comes from Phase 3A module.
- [ ] Verify company detail via `Companies` to `Manage`.
- [ ] Tier 2 field-by-field assertions: name, industry type, company type, address, postal code, email, phone.
- [ ] Delete created company at end of run.
- [ ] Assert deletion succeeded and record is gone.
- [ ] No raw selectors in tests; locators live in page classes.
- [ ] Locator priority followed: data-testid, role/name, stable attributes, justified text selectors.
- [ ] No `time.sleep()`.
- [ ] Use Playwright auto-waiting and `expect()`.
- [ ] Login once per session and share `storage_state`.
- [ ] Screenshot on failure attached to Allure.

### Phase 2B - Mobile Automation

- [ ] Maestro YAML flows plus Pytest wrapper.
- [ ] Allure integration shares one report style with web.
- [ ] App target: eWork SFA.
- [ ] Maestro CLI available and verified.
- [ ] Emulator/device visible through `adb devices`.
- [ ] Credentials via environment variables only.
- [ ] Prefer company created by web run.
- [ ] Fallback credentials only if needed, never committed, and documented in README only if used.
- [ ] Login scenario asserts dashboard displayed.
- [ ] Create customer scenario asserts created customer appears with correct data.
- [ ] Reusable login sub-flow via `runFlow`.
- [ ] Selector priority followed: id, id regex, text, accessibilityText, composite, point.
- [ ] Coordinate taps only as last resort with comment justification.
- [ ] No sleep-based waiting; use Maestro wait commands.
- [ ] Attach Maestro output and screen recording where possible to Allure.

### Phase 3A - AI-Generated Test Data

- [ ] Module requests coherent realistic Indonesian business data.
- [ ] Company data: legal name, email, phone, street address, industry.
- [ ] Customer data: name, contact, address.
- [ ] Schema validation before tests consume data.
- [ ] Invalid model output retries or falls back deterministically.
- [ ] No API key means deterministic Faker-style fallback, runnable offline and in CI.
- [ ] Actual data used attached to Allure.
- [ ] Token cost controlled deliberately.

### Phase 3B - AI Failure Triage

- [ ] Post-suite script reads Allure results.
- [ ] Produces Markdown or HTML triage report.
- [ ] Evaluates each failure in exact assignment order and stops at first match.
- [ ] Verdict categories: script/environment defect, product bug, flaky.
- [ ] Evidence included behind every verdict.
- [ ] AI never weakens, skips, rewrites assertions, swallows failures, or changes expected values to actual values.
- [ ] Failing tests stay failing.
- [ ] Triage remains human-review proposal only.
- [ ] Never auto-file or auto-close bugs.
- [ ] API key from environment only.

### Documentation And Evidence

- [ ] `README.md` covers dependencies, Playwright install, Maestro CLI, emulator/ADB, suite commands, and Allure commands.
- [ ] `AI_USAGE.md` covers model choice, AI execution points, exact prompts, invalid/unavailable behavior, and AI guardrails.
- [ ] Allure report from at least one full web run.
- [ ] Deliberately failing run and triage report.
- [ ] Clean modular repository structure.
- [ ] Optional only if safe: CI, parallel execution, genuine web-to-mobile company handoff.

## Repository Gap Analysis

- Current repository is a planning shell, not an automation project.
- Missing project structure for web tests, mobile flows, AI modules, reporting, generated data, and documentation.
- Missing dependency manifests and installation instructions.
- Missing `.env.example` and secret-handling convention.
- Missing manual test case workbook.
- Missing Allure configuration and result directories.
- Missing execution evidence and deliberate-failure evidence.
- Missing Git initialization or remote repository link, which affects final sheet deliverable.

## Ordered Execution Steps

1. Create manual test case workbook with exact required columns and assertion tiers.
2. Bootstrap Python project dependencies, Pytest, Playwright, Allure, configuration, fixtures, and secure environment handling.
3. Implement web login page objects, redirect handling, session storage, and dashboard assertion.
4. Implement AI test data module with schema validation, retry, deterministic fallback, and unit tests.
5. Implement web create-company wizard interactions and validation checks.
6. Implement web detail verification and cleanup with Tier 2 field assertions.
7. Harden full web run, selector usage, cleanup behavior, screenshots, and Allure evidence.
8. Bootstrap Maestro mobile flow structure, Pytest wrapper, Allure attachment support, and device checks.
9. Implement mobile login flow and dashboard assertion.
10. Implement mobile create-customer flow and Tier 2 assertions.
11. Implement genuine web-to-mobile data handoff if technically possible; otherwise document exact blocker.
12. Implement AI triage parser and report generator with guardrail tests.
13. Complete README and AI_USAGE documentation.
14. Produce deliberate-failure run, triage report, and restore the test afterward.
15. Create final audit with requirement-by-requirement evidence.
16. Run final feasible validation and prepare submission summary.

## Risks And Blockers

- Real eSuite access requires assignment-provided credentials via environment variables.
- Mobile work requires eWork SFA installed and a visible emulator/device.
- Maestro CLI is currently missing from PATH.
- Allure CLI and key Python reporting/test packages are currently missing.
- Product selectors are unknown until live exploration with Playwright/Maestro is possible.
- Shared environment cleanup is high risk; tests must preserve original failure while still attempting cleanup.
- New company to mobile login handoff may depend on product behavior not visible until live execution.
- No Git repository exists in this folder, so final GitHub link and version-control evidence are blocked until initialized or moved into a repo.

## Definition Of Done

- Every mandatory requirement from the PDF is either implemented and verified or documented with an exact blocker.
- Manual sheet, web suite, mobile suite, AI data module, AI triage module, README, AI_USAGE, Allure evidence, deliberate-failure triage evidence, and final audit exist.
- Credentials and API keys are never committed.
- Assertions are not weakened, skipped, swallowed, or changed to match actual values.
- Tier 2 assertions verify persisted data values, not only navigation or toasts.
- Created company data is cleaned up and deletion is asserted.
- No arbitrary sleeps exist in automation code or Maestro flows.
- Tests use maintainable page objects or reusable flows with selectors kept out of test files.
- Final report is honest about what was verified, what failed, and what remains blocked.
