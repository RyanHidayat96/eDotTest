from __future__ import annotations

from edot_qa.config import DEFAULT_BASE_URL, load_settings
from edot_qa.reporting.allure_metadata import metadata_for_node


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
