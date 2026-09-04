from __future__ import annotations

import json

import pytest

from edot_qa.config import DEFAULT_BASE_URL, load_settings
from edot_qa.reporting.allure_helpers import redact_payload
from edot_qa.reporting.allure_metadata import metadata_for_node
from edot_qa.web.pages.company_detail_page import CompanyDetailDataNotLoadedError, CompanyDetailPage
from tools.generate_allure_report import _ensure_step_evidence


def test_settings_default_to_assignment_target(monkeypatch):
    monkeypatch.delenv("ESUITE_BASE_URL", raising=False)
    settings = load_settings()
    assert settings.esuite_base_url == DEFAULT_BASE_URL


def test_settings_redacts_credentials(monkeypatch):
    monkeypatch.setenv("ESUITE_EMAIL", "secret@example.test")
    monkeypatch.setenv("ESUITE_PASSWORD", "secret-password")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    safe_settings = load_settings().as_safe_dict()
    assert safe_settings["ESUITE_EMAIL"] == "<set>"
    assert safe_settings["ESUITE_PASSWORD"] == "<set>"
    assert safe_settings["GEMINI_API_KEY"] == "<set>"
    assert "secret@example.test" not in str(safe_settings)
    assert "secret-password" not in str(safe_settings)
    assert "gemini-secret" not in str(safe_settings)


def test_allure_metadata_groups_company_flow_as_esuite_web():
    metadata = metadata_for_node(
        "tests/web/test_create_company.py::test_create_company_three_step_wizard_with_ai_data",
        {"web", "requires_cleanup"},
    )

    assert metadata.parent_suite == "eSuite Web"
    assert metadata.suite == "Web"
    assert metadata.sub_suite == "Company Registration"
    assert metadata.epic == "eSuite Web"
    assert metadata.feature == "Company Management"
    assert metadata.story == "Three Step Company Registration"
    assert metadata.test_case_id == "WEB-COMPANY-002"
    assert "requires_cleanup" in metadata.tags


def test_allure_metadata_groups_web_mobile_handoff_as_e2e():
    metadata = metadata_for_node(
        "tests/web/test_web_mobile_handoff.py::test_web_created_company_handoff_drives_mobile_login",
        {"e2e", "requires_device"},
    )

    assert metadata.parent_suite == "eDOT Cross Platform"
    assert metadata.suite == "E2E"
    assert metadata.sub_suite == "Web to Mobile Handoff"
    assert metadata.test_case_id == "E2E-WEB-MOBILE-001"
    assert "requires_device" in metadata.tags


def test_allure_payload_redacts_sensitive_values():
    redacted = redact_payload(
        {
            "email": "qa@example.test",
            "password": "secret",
            "nested": {"api_token": "token-value"},
        }
    )

    assert redacted["email"] == "qa@example.test"
    assert redacted["password"] == "<redacted>"
    assert redacted["nested"]["api_token"] == "<redacted>"


def test_allure_report_generator_adds_step_evidence(tmp_path):
    result = {
        "name": "test_sample",
        "fullName": "tests.web.test_sample#test_sample",
        "status": "passed",
        "labels": [{"name": "parentSuite", "value": "eSuite Web"}, {"name": "tag", "value": "web"}],
        "parameters": [{"name": "browser", "value": "chromium"}],
    }

    _ensure_step_evidence(result, tmp_path)

    assert result["steps"][0]["name"] == "Test summary"
    attachment = result["steps"][0]["attachments"][0]
    assert attachment["name"] == "Summary"
    payload = json.loads((tmp_path / attachment["source"]).read_text(encoding="utf-8"))
    assert payload["test"]["name"] == "test_sample"
    assert payload["suite"]["parentSuite"] == "eSuite Web"


def test_allure_report_generator_prunes_noisy_step_attachments(tmp_path):
    (tmp_path / "input.json").write_text(json.dumps({"field": "Email", "value": "qa@example.test"}), encoding="utf-8")
    result = {
        "name": "test_sample",
        "fullName": "tests.web.test_sample#test_sample",
        "status": "passed",
        "steps": [
            {
                "name": "Business step",
                "status": "passed",
                "attachments": [
                    {"name": "step-runtime-info", "source": "runtime.json"},
                    {"name": "step-result", "source": "result.json"},
                    {"name": "step-evidence-page", "source": "page.json"},
                    {"name": "step-input", "source": "input.json"},
                ],
                "steps": [{"name": "Empty technical step", "status": "passed", "attachments": [], "steps": []}],
            }
        ],
    }

    _ensure_step_evidence(result, tmp_path)

    assert len(result["steps"][0]["attachments"]) == 1
    attachment = result["steps"][0]["attachments"][0]
    assert attachment["name"] == "Inputs"
    payload = json.loads((tmp_path / attachment["source"]).read_text(encoding="utf-8"))
    assert payload == {"fields": {"Email": "qa@example.test"}}
    assert result["steps"][0]["steps"] == []


def test_company_detail_empty_name_reloads_five_times_before_error(monkeypatch):
    page = _ReloadOnlyPage()
    detail = CompanyDetailPage(page, settings=None)
    monkeypatch.setattr(detail, "expect_detail_shell_loaded", lambda: None)
    monkeypatch.setattr(detail, "_company_name_field_ready", lambda *args, **kwargs: False)
    monkeypatch.setattr(detail, "_company_name_field_current_value_now", lambda: "")

    with pytest.raises(CompanyDetailDataNotLoadedError):
        detail.refresh_until_company_name_loaded("PT Empty QA")

    assert page.reload_count == 5


def test_company_detail_reload_stops_when_company_name_loads(monkeypatch):
    page = _ReloadOnlyPage()
    detail = CompanyDetailPage(page, settings=None)
    readiness = iter([False, False, True])
    monkeypatch.setattr(detail, "expect_detail_shell_loaded", lambda: None)
    monkeypatch.setattr(detail, "_company_name_field_ready", lambda *args, **kwargs: next(readiness))
    monkeypatch.setattr(detail, "_company_name_field_current_value_now", lambda: "")

    detail.refresh_until_company_name_loaded("PT Ready QA")

    assert page.reload_count == 2


def test_company_detail_can_fail_fast_after_manage_reopen(monkeypatch):
    page = _ReloadOnlyPage()
    detail = CompanyDetailPage(page, settings=None)
    monkeypatch.setattr(detail, "expect_detail_shell_loaded", lambda: None)
    monkeypatch.setattr(detail, "_company_name_field_ready", lambda *args, **kwargs: False)
    monkeypatch.setattr(detail, "_company_name_field_current_value_now", lambda: "")

    with pytest.raises(CompanyDetailDataNotLoadedError):
        detail.refresh_until_company_name_loaded("PT Empty QA", max_reloads=0)

    assert page.reload_count == 0


def test_company_detail_visible_name_read_prevents_manage_reopen(monkeypatch):
    page = _ReloadOnlyPage()
    detail = CompanyDetailPage(page, settings=None)
    monkeypatch.setattr(detail, "expect_detail_shell_loaded", lambda: None)
    monkeypatch.setattr(detail, "_company_name_field_ready", lambda *args, **kwargs: False)
    monkeypatch.setattr(detail, "_company_name_field_current_value_now", lambda: "PT Visible QA")

    detail.refresh_until_company_name_loaded("PT Visible QA")

    assert page.reload_count == 0


def test_company_detail_wrong_visible_name_fails_without_reload(monkeypatch):
    page = _ReloadOnlyPage()
    detail = CompanyDetailPage(page, settings=None)
    monkeypatch.setattr(detail, "expect_detail_shell_loaded", lambda: None)
    monkeypatch.setattr(detail, "_company_name_field_ready", lambda *args, **kwargs: False)
    monkeypatch.setattr(detail, "_company_name_field_current_value_now", lambda: "PT Other QA")

    with pytest.raises(AssertionError, match="PT Other QA"):
        detail.refresh_until_company_name_loaded("PT Expected QA")

    assert page.reload_count == 0


class _ReloadOnlyPage:
    def __init__(self) -> None:
        self.reload_count = 0

    def reload(self, *, wait_until: str) -> None:
        assert wait_until == "domcontentloaded"
        self.reload_count += 1
