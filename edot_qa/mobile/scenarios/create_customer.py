from __future__ import annotations

from dataclasses import dataclass

from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.customer import MobileCustomerData, generate_mobile_customer_data
from edot_qa.mobile.customer_list import customer_card_address_from_maestro_result, find_created_customer_card
from edot_qa.mobile.runtime import require_customer_runtime, start_app_from_stored_session
from edot_qa.mobile.scenarios.types import MaestroFlow
from edot_qa.reporting.allure_helpers import allure_step


@dataclass(frozen=True)
class MobileCreateCustomerScenario:
    settings: MobileSettings
    run_flow: MaestroFlow

    def run(self) -> MobileCustomerData:
        with allure_step(
            "Create customer and verify list card. Expected: submitted customer appears on New Customer List",
            screenshot=False,
            force=True,
        ):
            context = require_customer_runtime(self.settings)
            start_app_from_stored_session(context)

            customer = generate_mobile_customer_data()
            customer_env = customer.as_maestro_env()
            result = self.run_flow(
                "create_customer.yaml",
                extra_env=customer_env,
                step_title="Create eWork customer",
                expected="New Customer List page is displayed",
            )
            customer_card_address = customer_card_address_from_maestro_result(result)

            find_created_customer_card(
                customer,
                customer_card_address=customer_card_address,
                settings=self.settings,
                device=context.device,
            )
            return customer
