# Execution Evidence

Generated evidence belongs here after the final execution step.

- `web-allure/`: Allure HTML report from the required web scenarios.
- `deliberate-allure/`: Allure HTML report from the isolated deliberate-failure run.
- `triage/triage-report.md`: human-review triage proposal for the deliberate failure.

Do not place `.env`, storage state, cookies, API keys, passwords, or raw secret headers here.
Run `npm run evidence:scan` before packaging or sharing evidence.
