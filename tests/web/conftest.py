from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from edot_qa.config import Settings, load_settings
from edot_qa.reporting.allure_helpers import attach_json, attach_page_evidence, attach_png, attach_text
from edot_qa.web.scenarios.login import EsuiteLoginScenario
from edot_qa.web.session_state import has_storage_state, new_context


@pytest.fixture(scope="session")
def settings() -> Settings:
    loaded_settings = load_settings()
    loaded_settings.ensure_runtime_dirs()
    attach_json("runtime-settings", loaded_settings.as_safe_dict())
    return loaded_settings


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright, settings: Settings) -> Browser:
    browser_type = getattr(playwright_instance, settings.browser)
    browser_instance = browser_type.launch(
        headless=settings.headless,
        slow_mo=settings.slow_mo_ms,
    )
    yield browser_instance
    browser_instance.close()


@pytest.fixture(scope="session")
def esuite_storage_state(settings: Settings) -> Path:
    if has_storage_state(settings):
        attach_json(
            "storage-state",
            {"status": "reused", "path": str(settings.storage_state_path)},
        )
        return settings.storage_state_path
    if not settings.has_esuite_credentials:
        pytest.skip("Missing ESUITE_EMAIL/ESUITE_PASSWORD and no storage_state file exists")

    with sync_playwright() as playwright:
        browser_type = getattr(playwright, settings.browser)
        browser_instance = browser_type.launch(
            headless=settings.headless,
            slow_mo=settings.slow_mo_ms,
        )
        context = new_context(browser_instance, settings)
        page = context.new_page()
        try:
            EsuiteLoginScenario(page, settings).run()
        except Exception:
            if not page.is_closed():
                try:
                    attach_png("login-setup-failure-screenshot", page.screenshot(full_page=True))
                except Exception as screenshot_error:
                    attach_text("login-setup-screenshot-error", str(screenshot_error))
            raise
        finally:
            context.close()
            browser_instance.close()

    attach_json(
        "storage-state",
        {"status": "created", "path": str(settings.storage_state_path)},
    )
    return settings.storage_state_path


@pytest.fixture()
def context(browser: Browser, settings: Settings) -> BrowserContext:
    browser_context = new_context(browser, settings)
    yield browser_context
    browser_context.close()


@pytest.fixture()
def authenticated_context(esuite_storage_state: Path, browser: Browser, settings: Settings) -> BrowserContext:
    browser_context = new_context(browser, settings, use_storage_state=True)
    yield browser_context
    browser_context.close()


@pytest.fixture()
def page(context: BrowserContext) -> Page:
    page_instance = context.new_page()
    yield page_instance
    page_instance.close()


@pytest.fixture()
def authenticated_page(authenticated_context: BrowserContext, settings: Settings) -> Page:
    page_instance = authenticated_context.new_page()
    page_instance.goto(settings.esuite_base_url)
    page_instance.wait_for_load_state("domcontentloaded")
    attach_page_evidence("Authenticated eSuite landing", page_instance, screenshot=True)
    yield page_instance
    page_instance.close()
