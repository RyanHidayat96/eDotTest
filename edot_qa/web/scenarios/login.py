from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page

from edot_qa.config import Settings
from edot_qa.reporting.allure_helpers import allure_step, attach_json
from edot_qa.web.pages.dashboard_page import DashboardPage
from edot_qa.web.pages.login_page import LoginPage
from edot_qa.web.session_state import save_storage_state


@dataclass(frozen=True)
class WebLoginResult:
    current_location: str
    storage_state_path: Path


@dataclass(frozen=True)
class EsuiteLoginScenario:
    page: Page
    settings: Settings

    def run(self) -> WebLoginResult:
        with allure_step("Login with eSuite credentials", page=self.page, screenshot=False):
            LoginPage(self.page, self.settings).login(
                self.settings.esuite_email or "",
                self.settings.esuite_password or "",
            )

        with allure_step("Verify dashboard greeting after login", page=self.page, screenshot=True):
            DashboardPage(self.page, self.settings).expect_loaded()

        with allure_step(
            "Persist storage state after successful login",
            data={"path": self.settings.storage_state_path},
        ):
            save_storage_state(self.page.context, self.settings.storage_state_path)

        result = WebLoginResult(
            current_location=_safe_current_location(self.page.url),
            storage_state_path=self.settings.storage_state_path,
        )
        attach_json(
            "login-verification",
            {
                "assertion": "Login inputs credentials and Welcome Back, greeting is visible",
                "storage_state_path": str(result.storage_state_path),
                "current_location": result.current_location,
            },
        )
        return result


def _safe_current_location(url: str) -> str:
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
