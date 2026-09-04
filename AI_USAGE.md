# AI Usage

This project has two runtime AI capabilities required by the eDOT QA Automation Take-Home V4 assignment:

1. AI-generated test data for web company and mobile customer flows.
2. AI-assisted failure triage after Allure results exist.

Both features are optional at runtime. When no API key is present, deterministic code still runs.

## Models

Default test-data model:

```text
GEMINI_TEST_DATA_MODEL=gemini-3.1-flash-lite
```

Default triage model:

```text
GEMINI_TRIAGE_MODEL=gemini-3.1-flash-lite
```

The model is environment-configured so it can be changed without editing tests. `gemini-3.1-flash-lite` is used because the suite needs compact structured JSON generation, concise failure notes, low token cost, and practical runtime latency. Deterministic validation remains the source of control; model output is never trusted directly.

## Runtime Stages

Test data AI runs before tests consume data. `edot_qa.ai.test_data.TestDataGenerator` calls Gemini only when `GEMINI_API_KEY` exists, then validates the response before returning data to web or mobile tests.

Failure triage AI runs after test execution. `tools/triage_allure_failures.py` reads Allure result JSON files, creates deterministic verdicts and evidence first, then optionally asks Gemini for a short human-review note. Current code does not let AI override the deterministic verdict. Step 8 will strengthen this triage implementation further; this file must be updated in that same step if prompts or schema behavior change.

AI-assisted code authoring may have been used during development, but no project script rewrites submitted assertions or expected values.

## API Key Handling

Supported API key variable:

```text
GEMINI_API_KEY=
```

The key must come from local `.env` or the process environment. `.env` is ignored by Git. API keys are not stored in source, YAML flows, handoff files, test data files, or documentation.

## Test Data Prompt

Code location: `edot_qa.ai.test_data.build_prompt`.

Exact current prompt template:

```text
Generate coherent realistic Indonesian business test data for eDOT QA automation. Return only JSON matching the provided schema. Use safe dummy domains and phone numbers. Make values unique for run_id {run_id}. Company must include legal_name, email, phone, street_address, industry. Customer must include name, contact, address. Do not include credentials, API keys, real private personal data, or extra fields.
```

## Test Data Schema Validation

Code location: `edot_qa.ai.test_data`.

Pydantic models:

- `CompanyData`
- `CustomerData`
- `BusinessTestData`
- `GeneratedTestData`

Each model uses `ConfigDict(extra="forbid")`, so unexpected fields are rejected. Company data validates:

- `legal_name` starts with `PT ` or `CV `
- `email` matches email format
- `phone` matches Indonesian `+62` format
- required fields: `legal_name`, `email`, `phone`, `street_address`, `industry`

Customer data validates:

- `contact` is either Indonesian `+62` phone or email
- required fields: `name`, `contact`, `address`

The Gemini request also sends a JSON response schema derived from `business_test_data_json_schema()`. The returned text is parsed as JSON and then validated with Pydantic before any test uses it.

## Test Data Retry And Fallback

Token and retry controls:

```text
AI_TEST_DATA_MAX_ATTEMPTS=2
AI_TEST_DATA_MAX_OUTPUT_TOKENS=700
```

Fallback behavior:

- Missing `GEMINI_API_KEY`: use deterministic Faker fallback with reason `missing_api_key`.
- HTTP 404 model error: stop retrying and use fallback with reason `model_not_found`.
- Other Gemini request failure: stop retrying and use fallback with reason `api_request_failed`.
- Malformed JSON or schema-invalid output: retry up to `AI_TEST_DATA_MAX_ATTEMPTS`.
- Still invalid after all attempts: use fallback with reason `invalid_model_output_after_<attempts>_attempts`.

Fallback provider:

- class: `FakerFallbackProvider`
- locale: `id_ID`
- seed: first 8 hex chars from `sha256(run_id)`
- uniqueness: generated values include the run ID suffix

The actual data used, whether AI-generated or fallback, is attached to Allure as `ai-test-data-used`. Generation errors are attached as `ai-test-data-generation-errors`. Secret values are not included.

## Triage Prompt

Code location: `edot_qa.ai.triage.build_triage_prompt`.

Exact current prompt template:

```text
Review deterministic QA failure triage. Do not change verdict. Do not weaken, skip, or rewrite assertions. Do not swallow failures. Do not change expected values to actual values. Do not auto-file or auto-close bugs. Return at most 3 concise bullets for human review.
Test: {test_name}
Status: {status}
Verdict: {verdict}
Matched rule: {matched_rule}
Evidence:
- {evidence_item_1}
- {evidence_item_2}
```

Only the first eight deterministic evidence items are sent to keep the prompt bounded.

## Triage Decision Process

Code location: `edot_qa.ai.triage.classify_failure`.

The deterministic classifier checks evidence in the assignment order and stops at the first decisive match:

1. Failure type: exception vs failed assertion.
2. Locator uniqueness: ambiguous, non-unique, or wrong locator evidence.
3. Preconditions and prior steps: setup, credentials, auth, device, Maestro, ADB, storage state.
4. Expected value validity: stale or invalid expected data.
5. Reproducibility: mixed passed and failed outcomes for the same test.

Allowed verdict strings:

```text
script/environment defect
product bug
flaky
```

Current AI participation is limited to an optional note after deterministic classification. The note is sanitized and rejected when it suggests forbidden behavior. The report remains a human-review proposal.

## Triage Fallback

Token control:

```text
AI_TRIAGE_MAX_OUTPUT_TOKENS=900
```

Fallback behavior:

- Missing `GEMINI_API_KEY`: triage writes deterministic Markdown only.
- Gemini request failure: deterministic verdict remains; evidence records that the AI note was unavailable.
- Empty or unsafe note: note is rejected; deterministic verdict remains.

## Guardrails

AI is forbidden to:

- weaken assertions
- skip failing assertions
- rewrite expected values
- change expected values to actual values
- swallow failures in `try/except`
- turn a failing test into a passing test
- file bugs automatically
- close bugs automatically
- store or print API keys, passwords, cookies, or bearer tokens

These restrictions exist because the assignment grades real behavior verification. AI may help generate data and propose triage notes, but it must not hide defects or alter test outcomes.

## Secret Handling

Sensitive runtime values come from environment variables only. Safe reporting helpers redact configured secrets before attaching commands or environment context to Allure. Reports should not expose credentials, API keys, storage state JSON, cookies, or authorization headers.

Before packaging or sharing evidence, run:

```bash
python tools/check_submission_safety.py
```
