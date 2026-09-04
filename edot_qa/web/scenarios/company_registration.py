from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page

from edot_qa.ai.test_data import generate_test_data
from edot_qa.config import Settings
from edot_qa.reporting.allure_helpers import allure_step, attach_json, attach_text
from edot_qa.web.company_registration import CompanyRegistrationData
from edot_qa.web.pages.companies_page import CompaniesPage
from edot_qa.web.pages.company_detail_page import CompanyDetailPage
from edot_qa.web.pages.company_manage_page import CompanyManagePage


@dataclass(frozen=True)
class CompanyRegistrationResult:
    registration: CompanyRegistrationData
    company_id: str | None


@dataclass(frozen=True)
class CompanyRegistrationScenario:
    page: Page
    settings: Settings

    def create_verify_and_cleanup(self) -> CompanyRegistrationResult:
        registration = prepare_company_registration_data()
        primary_error: Exception | None = None
        created_company_id: str | None = None
        detail_page: CompanyDetailPage | None = None
        try:
            with allure_step("Create company through three step wizard", page=self.page):
                wizard = CompaniesPage(self.page, self.settings).open_register_company_wizard()
                wizard.complete_three_step_registration(registration)

            with allure_step("Verify created company in Manage and Detail", page=self.page, screenshot=True):
                manage_page = CompaniesPage(self.page, self.settings).open_manage()
                # Tier 2: created record must display submitted company name in Manage, not only a success toast.
                manage_page.expect_company_present(registration.company_name)
                detail_page = manage_page.open_company_detail(registration.company_name)
                detail_page.expect_company_values(registration)
                created_company_id = detail_page.company_id_value()
            return CompanyRegistrationResult(registration=registration, company_id=created_company_id)
        except Exception as error:
            primary_error = error
            raise
        finally:
            try:
                self.cleanup_created_company(registration, created_company_id, detail_page=detail_page)
            except Exception as cleanup_error:
                attach_text("company-cleanup-error", str(cleanup_error))
                if primary_error is None:
                    raise

    def cleanup_created_company(
        self,
        registration: CompanyRegistrationData,
        company_id: str | None,
        *,
        detail_page: CompanyDetailPage | None = None,
    ) -> None:
        with allure_step(
            "Cleanup created company",
            page=self.page,
            screenshot=True,
            data={"company_name": registration.company_name, "company_id": company_id},
        ):
            if detail_page is not None and "/profile" in self.page.url:
                detail_page.delete_current_company()
                cleanup_page = CompanyManagePage(self.page, self.settings)
            else:
                cleanup_page = CompaniesPage(self.page, self.settings).open_manage()
                cleanup_page.delete_company_if_present(registration.company_name)

            cleanup_page.expect_company_absent(registration.company_name, company_id=company_id)


def prepare_company_registration_data() -> CompanyRegistrationData:
    with allure_step("Prepare company registration data", screenshot=False):
        generated_data = generate_test_data()
        registration = CompanyRegistrationData.from_generated_test_data(generated_data)
        attach_json("company-registration-data", registration.as_allure_payload())
        return registration
