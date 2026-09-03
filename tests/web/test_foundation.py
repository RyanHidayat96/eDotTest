from __future__ import annotations

from edot_qa.config import DEFAULT_BASE_URL, load_settings


def test_settings_default_to_assignment_target(monkeypatch):
    monkeypatch.delenv("ESUITE_BASE_URL", raising=False)
    settings = load_settings()
    assert settings.esuite_base_url == DEFAULT_BASE_URL


def test_settings_redacts_credentials(monkeypatch):
    monkeypatch.setenv("ESUITE_EMAIL", "secret@example.test")
    monkeypatch.setenv("ESUITE_PASSWORD", "secret-password")
    safe_settings = load_settings().as_safe_dict()
    assert safe_settings["ESUITE_EMAIL"] == "<set>"
    assert safe_settings["ESUITE_PASSWORD"] == "<set>"
    assert "secret@example.test" not in str(safe_settings)
    assert "secret-password" not in str(safe_settings)
