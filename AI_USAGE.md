# AI Usage

This project includes two runtime AI capabilities required by the eDOT QA Automation Take-Home V4 assignment: AI-generated test data and AI-assisted failure triage. Both are optional at runtime when no API key is present, so the suite still runs offline and in CI.

## Model

Default model: `gpt-5-nano`.

Why this model:

- The tasks are structured and low-context: create one compact JSON test-data payload or summarize one already-classified failure.
- Cost control matters more than long-form reasoning.
- Deterministic code performs validation and classification first, so the model is never trusted as the only control.

The model can be changed through environment variables:

```text
OPENAI_TEST_DATA_MODEL=gpt-5-nano
OPENAI_TRIAGE_MODEL=gpt-5-nano
```

## Where AI Runs

- While writing tests: AI-assisted development was used to draft and refine code, but no repository script rewrites submitted tests or assertions.
- During test runs: `edot_qa.ai.test_data.TestDataGenerator` calls the OpenAI Responses API only when `OPENAI_API_KEY` is set. It generates Indonesian business data before web/mobile tests consume it.
- After test runs: `tools/triage_allure_failures.py` reads Allure results. Deterministic evidence collection and verdict classification run first. Optional AI notes run only after that evidence exists.

## API Key Handling

The only API key variable is:

```text
OPENAI_API_KEY=
```

It must be set locally in `.env` or the process environment. `.env` is ignored by Git. API keys are never written to reports, handoff files, YAML flows, or tests.

## Test Data Prompt

Code location: `edot_qa.ai.test_data.build_prompt`.

Exact prompt template:

```text
Generate coherent realistic Indonesian business test data for eDOT QA automation. Return only JSON matching the provided schema. Use safe dummy domains and phone numbers. Make values unique for run_id {run_id}. Company must include legal_name, email, phone, street_address, industry. Customer must include name, contact, address. Do not include credentials, API keys, real private personal data, or extra fields.
```

The prompt is sent with a strict JSON schema from `business_test_data_json_schema()`. Required company fields are legal name, email, phone, street address, and industry. Required customer fields are name, contact, and address.

Token controls:

```text
AI_TEST_DATA_MAX_ATTEMPTS=2
AI_TEST_DATA_MAX_OUTPUT_TOKENS=700
```

Unavailable or invalid behavior:

- If `OPENAI_API_KEY` is absent, the generator uses deterministic Faker fallback.
- If the model returns malformed JSON or schema-invalid data, the generator retries up to `AI_TEST_DATA_MAX_ATTEMPTS`.
- If all attempts fail, it uses deterministic Faker fallback.
- The actual data used is attached to Allure as `ai-test-data-used`.

## Triage Prompt

Code location: `edot_qa.ai.triage.build_triage_prompt`.

Exact prompt template:

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

Only the first eight deterministic evidence items are sent to control tokens.

Token control:

```text
AI_TRIAGE_MAX_OUTPUT_TOKENS=900
```

Unavailable or invalid behavior:

- If `OPENAI_API_KEY` is absent, triage still writes a Markdown report using deterministic verdicts only.
- If the OpenAI request fails, the report keeps the deterministic verdict and records that the AI note was unavailable.
- If the AI note suggests a forbidden action, the note is rejected and the deterministic verdict remains unchanged.

## Deterministic Triage Order

For each failed or broken Allure result, `edot_qa.ai.triage.classify_failure` walks evidence in the assignment order and stops at the first decisive match:

1. Exception or failed assertion.
2. Locator uniqueness.
3. Preconditions and prior steps.
4. Expected value correctness.
5. Reproducibility.

Verdict categories are exactly:

- `script/environment defect`
- `product bug`
- `flaky`

The report always includes evidence for the verdict. A product-bug verdict remains a human-review proposal, not an automatic bug.

## AI Guardrails

AI is deliberately forbidden to:

- Weaken, skip, or rewrite assertions.
- Swallow failures in `try/except`.
- Change expected values to actual values.
- Make a failing test pass.
- File bugs automatically.
- Close bugs automatically.
- Store or print API keys.

Why: the assignment grades real behavior verification. Letting AI mutate assertions or expected values would hide product defects, create false green builds, and make the evidence untrustworthy.

## Offline and CI Behavior

The suite is designed to run without AI credentials:

- Test data falls back to deterministic Faker output.
- Triage falls back to deterministic Markdown output.
- Unit tests use fake providers and do not perform network calls.

This keeps CI stable and prevents network or quota problems from blocking non-AI validation.
