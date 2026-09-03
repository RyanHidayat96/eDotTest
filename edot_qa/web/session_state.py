from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, BrowserContext

from edot_qa.config import Settings


def has_storage_state(settings: Settings) -> bool:
    return settings.storage_state_path.is_file()


def new_context(browser: Browser, settings: Settings, *, use_storage_state: bool = False) -> BrowserContext:
    context_options = {
        "base_url": settings.esuite_base_url,
        "ignore_https_errors": True,
    }
    if use_storage_state and has_storage_state(settings):
        context_options["storage_state"] = str(settings.storage_state_path)
    return browser.new_context(**context_options)


def save_storage_state(context: BrowserContext, storage_state_path: Path) -> None:
    storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(storage_state_path))
