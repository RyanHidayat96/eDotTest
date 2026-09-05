# Execution Evidence

Generated evidence belongs in the shared Allure output after the final execution step.

- `reports/allure-results/`: shared raw web, mobile, and evidence results.
- `reports/allure-report/`: shared Allure HTML report.
- `reports/triage/triage-report.md`: human-review triage proposal attached by `allure:generate`.
- Deliberate failure is intentionally red only at raw pytest time; `allure:generate` marks it as expected evidence.

Do not place `.env`, storage state, cookies, API keys, passwords, or raw secret headers here.
The evidence command runs a secret scan automatically before finishing.
