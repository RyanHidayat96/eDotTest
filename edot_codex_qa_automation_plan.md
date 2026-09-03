# Codex Agent — eDOT QA Automation Take-Home V4

## Mission
Implement the complete eDOT QA Automation Take-Home Test V4 from the attached assignment, with production-quality, reviewable code and evidence.

**Source of truth:** the provided `Take-Home Test QA Automation Engineer eDOT V4.pdf`. Do not invent requirements. Preserve every mandatory requirement, assertion tier, guardrail, and deliverable.

## Critical execution rule
Work **strictly one phase/step at a time**.

- Start at **STEP 0** only.
- After completing a step, STOP.
- Do **not** continue automatically.
- Continue only when the user explicitly types **`next`**.
- On each step: inspect the existing repository first, implement/test only that step, verify it, and report a minimal completion summary.
- Never redo completed work unless verification shows it is necessary.
- If blocked, diagnose the blocker and STOP rather than silently bypassing requirements.
- Do not weaken assertions, skip mandatory work, hardcode secrets, or fabricate evidence.

## Assignment requirements

### Phase 1 — Manual Test Case Design
Create an Excel/Google-Sheet-ready test case document covering:

**Web (eSuite)**
1. Login
2. Create a new company
3. Verify created-company data in detail view

**Mobile (eWork SFA)**
4. Login using newly created company credentials
5. Create a customer

Required columns exactly:
`Test Case ID | Title / Description | Precondition | Test Steps | Test Data (exact values) | Expected Result | Assertion Tier | Status`

Assertion rules:
- Tier 1 = navigation/display only.
- Tier 2 = create/edit/delete: verify record existence and actual values, not only toast.
- Delete = assert record gone.
- Edit = assert changed value.
- Negative = assert the specific error message.
- Mark Tier 2 assertions in automation code with a short comment.

### Phase 2A — Web
Stack:
- Python + Pytest
- Playwright
- Page Object Model
- Allure
- Target: `https://esuite.edot.id`

Credentials must come from environment variables/secrets. Never commit credentials.

Login:
- Click `Use Email or Username`
- Submit email
- Submit password
- Handle redirect through eDOT Account Center and back inside page objects.
- Assert dashboard greeting `Welcome Back,`.

Create company:
- `Companies → + Add Company`
- 3-step Register Company wizard.
- Step 1 fields:
  - Company Name
  - Email
  - Phone
  - Industry Type
  - Company Type
  - Language
  - Street Address
  - dependent cascade: Country → Province → City → District → Zone → Postal Code
- Next must remain disabled until valid.
- Test data comes from Phase 3A AI generator.

Verify detail:
Open through `Companies → Manage`.
Tier 2, field-by-field:
- name
- industry type
- company type
- address
- postal code
- email
- phone

Cleanup:
- Delete the created company at end of run.
- Assert deletion succeeded / record is gone.
- Shared environment must not contain leftovers.

Web engineering:
- Locators only in page classes.
- No raw selectors in tests.
- Locator priority:
  1. `data-testid`
  2. role + accessible name
  3. stable `name` / `id` / `aria-*`
  4. text last; justify text selectors in comments.
- No `time.sleep()`.
- Use Playwright auto-waiting and `expect()`.
- Login once per session and share auth with `storage_state`.
- Screenshot on failure attached to Allure.

### Phase 2B — Mobile
Stack:
- Maestro + Pytest wrapper
- Python + Pytest
- Allure
- App: eWork SFA
- Maestro CLI
- emulator/device visible through `adb devices`

Credentials:
- Prefer the company created by web.
- New company has 30-day trial.
- Fallback credentials are supplied by the assignment; never commit them. If fallback is used, document it in README.

Scenarios:
- Login → assert dashboard displayed.
- Create customer → Tier 2: assert created customer appears with correct data.

Mobile engineering:
- Flows are YAML.
- Pytest wrapper invokes flows so web/mobile share one Allure run.
- Reusable flows must use `runFlow`.
- Extract shared login into reusable sub-flow.
- Credentials and test data via environment variables.
- Never hardcode credentials in YAML.
- Selector priority:
  1. id
  2. id regex
  3. text
  4. accessibilityText
  5. composite
  6. point
- Coordinate tap only as last resort and justify in comment.
- No sleep-based waiting; use Maestro wait commands.
- Attach Maestro output and screen recording where possible to Allure.

### Phase 3A — AI-generated test data
Build a module that asks a model for coherent realistic Indonesian business data.

Company:
- legal name
- email
- phone
- street address
- industry

Customer:
- name
- contact
- address

Requirements:
- Validate model output against a schema before use.
- Invalid output → retry or deterministic fallback.
- If no API key → automatically use deterministic Faker fallback.
- Must run offline and in CI without AI credentials.
- Attach the actual data used to Allure.
- Be deliberate about token cost.

### Phase 3B — AI failure triage
Create a post-suite script that reads Allure results and produces Markdown or HTML triage report.

For every failure, evaluate in this exact order and stop at first match:
1. Exception (element not found/timeout) or failed assertion?
   - Exception is almost always script/environment, not product bug.
2. Did locator resolve to intended unique element?
3. Did every step before assertion succeed and were preconditions met?
4. Was expected value correct according to test case?
5. Does failure reproduce consistently?
   - intermittent = flaky.

Verdict categories:
- script/environment defect
- product bug
- flaky

Report evidence behind every verdict.

AI guardrails:
- AI must NEVER weaken, skip, or rewrite assertions.
- AI must NEVER swallow failures.
- AI must NEVER change expected values to actual values.
- A failing test stays failing.
- Triage is only a human-review proposal.
- Never auto-file bugs.
- Never auto-close bugs.
- API key from environment only.
- Never commit API keys.

### AI_USAGE.md
Document:
- model and why
- where AI runs: writing tests / during run / after run
- exact prompts
- invalid/unavailable behavior
- what AI is deliberately forbidden to do and why

### Deliverables
- Manual test case Excel/Google Sheet-ready document with GitHub repo link.
- Clean modular repository.
- Web Playwright + Pytest.
- Mobile Maestro YAML + Pytest wrappers.
- Both AI modules.
- Allure setup.
- README with:
  - dependencies
  - Playwright install
  - Maestro CLI
  - emulator/adb
  - each suite execution
  - Allure generation/opening
- AI_USAGE.md
- Evidence:
  - Allure report from at least one full web run.
  - deliberately failing run and triage report.
- Optional bonus:
  - CI
  - parallel execution
  - genuine web→mobile company data handoff

## Quality gates
Before declaring any step complete:
- Inspect existing code and repository structure.
- Keep architecture modular and maintainable.
- Prefer deterministic behavior.
- Never use arbitrary sleeps.
- Never hide failures.
- Never weaken assertions to make tests green.
- Never change expected values based on actual output.
- Never commit secrets.
- Add meaningful logs/evidence where useful.
- Verify changed code with the narrowest relevant tests/checks.
- Keep changes explainable by a QA Automation Engineer.

# Controlled execution plan

## STEP 0 — Repository reconnaissance + implementation plan
Do only:
1. Inspect repository tree.
2. Identify existing stack, package/config files, test directories, CI, README, env examples.
3. Check current git status.
4. Identify what is already implemented versus missing.
5. Check installed/runtime availability relevant to the project where practical.
6. Create/update a concise `IMPLEMENTATION_PLAN.md` containing:
   - requirements checklist
   - repository gap analysis
   - ordered execution steps
   - risks/blockers
   - definition of done
7. Do not implement the actual test suite yet.

STOP. Wait for `next`.

## STEP 1 — Phase 1 test-case design
Implement only the manual test case document.
- Cover all required web/mobile scenarios.
- Make test cases behavior-focused and sufficiently detailed.
- Include exact test data strategy/placeholders consistent with AI-generated data.
- Correctly assign assertion tiers.
- Include positive and necessary negative coverage where supported by the assignment.
- Include cleanup.
- Ensure every test case maps to later automation.

Verify the spreadsheet opens correctly and is reviewable.

STOP. Wait for `next`.

## STEP 2 — Web test architecture/bootstrap
Implement only the web automation foundation:
- dependencies
- pytest configuration
- Playwright setup
- Allure integration
- page-object base/foundation
- browser/session fixtures
- environment configuration
- storage-state authentication architecture
- failure screenshot attachment
- secure `.env` handling and `.env.example`
- repository hygiene

Do not implement the full company workflow yet.

STOP. Wait for `next`.

## STEP 3 — Web login
Implement only:
- login page objects
- eDOT Account Center redirect handling
- one-session authentication/storage state
- dashboard greeting assertion
- focused test(s)
- Allure evidence

Verify with the real target if credentials/environment are available.

STOP. Wait for `next`.

## STEP 4 — AI test-data module
Implement Phase 3A completely:
- provider abstraction
- model integration
- schema
- validation
- retry
- deterministic Faker fallback
- offline/CI behavior
- secure environment configuration
- Allure attachment of actual generated/fallback data
- token-cost controls
- focused unit tests

Do not yet wire the data into the company UI workflow.

STOP. Wait for `next`.

## STEP 5 — Web create-company workflow
Implement the complete 3-step company wizard:
- page objects
- all fields
- dependent cascade
- validation/disabled Next behavior
- AI-generated data integration
- robust selectors
- Tier 2 assertions
- Allure evidence

Do not skip fields.

STOP. Wait for `next`.

## STEP 6 — Web company detail verification + cleanup
Implement:
- Companies → Manage navigation
- field-by-field Tier 2 verification
- delete cleanup
- deletion verification
- cleanup-on-failure strategy that does not hide the original failure
- relevant Allure evidence

STOP. Wait for `next`.

## STEP 7 — Web full-run hardening
Run and harden the complete web suite:
- session reuse
- deterministic cleanup
- no sleeps
- selector review
- assertion review
- failure screenshots
- Allure
- flaky-risk review
- verify no secrets tracked
- full web execution evidence

STOP. Wait for `next`.

## STEP 8 — Mobile foundation
Implement only:
- Maestro project structure
- Pytest wrapper
- Allure integration
- environment-variable configuration
- device/ADB checks
- reusable flow architecture
- shared login `runFlow`
- no hardcoded credentials

STOP. Wait for `next`.

## STEP 9 — Mobile login
Implement:
- login flow
- selector discovery/verification
- environment credentials
- dashboard assertion
- Maestro output/screenshot/recording attachment where possible
- focused Pytest wrapper

STOP. Wait for `next`.

## STEP 10 — Mobile create-customer
Implement:
- customer creation flow
- test data integration
- Tier 2 field/data assertions
- reusable sub-flows
- cleanup if applicable/required by actual product behavior
- Allure evidence

STOP. Wait for `next`.

## STEP 11 — Web → Mobile data handoff
Implement the genuine company-data handoff:
- web creates company
- securely persists only required runtime data
- mobile consumes it
- no secrets committed
- fallback path remains documented
- validate end-to-end handoff

If technically impossible due to environment/product constraints, document the exact blocker rather than faking it.

STOP. Wait for `next`.

## STEP 12 — AI triage
Implement Phase 3B:
- parse Allure results
- deterministic evidence collection first
- AI triage only after required evidence is collected
- exact decision order from assignment
- verdict + evidence per failure
- Markdown/HTML output
- token-efficient prompts
- API-key environment handling
- no assertion/test mutation
- no auto bug filing/closing
- tests for triage logic

STOP. Wait for `next`.

## STEP 13 — AI_USAGE.md + README
Complete documentation:
- exact AI model/purpose
- exact prompts
- AI execution points
- invalid/unavailable behavior
- guardrails
- installation
- Playwright
- Maestro
- ADB/emulator
- environment variables
- web/mobile commands
- Allure commands
- triage command
- fallback credentials note only if actually used
- architecture and troubleshooting

STOP. Wait for `next`.

## STEP 14 — Deliberate failure + triage evidence
Create a controlled temporary failure (e.g. intentionally wrong locator), execute it, confirm:
- test genuinely fails
- original assertion is not weakened
- triage identifies the correct category using evidence
- triage report is generated

Restore the test afterward.

STOP. Wait for `next`.

## STEP 15 — Final audit
Perform a strict assignment audit:
- every requirement checked
- every deliverable present
- Tier 2 assertions correct
- selectors comply
- no sleeps
- no secrets
- cleanup works
- Allure evidence exists
- AI data schema/fallback works
- AI triage works
- guardrails enforced
- README/AI_USAGE complete
- Git status clean of secrets/generated junk as appropriate
- optional bonus only if safe and genuinely working

Create `FINAL_AUDIT.md` with pass/fail/evidence for every requirement.

STOP. Wait for `next`.

## STEP 16 — Final execution/review
Only after explicit `next`:
- run the most complete feasible validation
- inspect failures
- fix only legitimate defects
- regenerate final evidence
- ensure deliberate-failure test is restored
- prepare concise submission summary
- do not claim anything that was not actually verified.

STOP.

# Coding behavior
- Use existing project conventions when good; do not rewrite working code unnecessarily.
- If a requirement conflicts with existing architecture, prioritize the assignment and document the change.
- Ask the user only when a decision truly cannot be determined from the repository or assignment.
- Never expose secrets in logs, reports, commits, or generated documentation.
- Use environment variables for all credentials/API keys.
- Make tests fail for the right reasons.
- Prefer semantic/accessibility selectors over brittle CSS/XPath.
- Keep test files focused on behavior; page/flow classes own interaction details.
- Every Tier 2 assertion must have a concise code comment identifying it.
- For failures, preserve original evidence and failure state.
- When a tool/dependency is unavailable, report it explicitly and continue only with work that remains valid.

# Output discipline
After each step, respond with only:
- `STEP X DONE` + 1–3 bullets of what changed
- verification result
- blockers, if any

Then wait for `next`.
