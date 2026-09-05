from __future__ import annotations

from dataclasses import dataclass

from edot_qa.mobile.config import MobileSettings
from edot_qa.mobile.customer import MobileCustomerData, generate_mobile_customer_data
from edot_qa.mobile.customer_list import customer_card_address_from_maestro_result, find_created_customer_card
from edot_qa.mobile.runtime import require_customer_runtime, start_app_from_stored_session
from edot_qa.mobile.scenarios.types import MaestroFlow


@dataclass(frozen=True)
class MobileCreateCustomerScenario:
    settings: MobileSettings
    run_flow: MaestroFlow

    def run(self) -> MobileCustomerData:
        context = require_customer_runtime(self.settings)
        start_app_from_stored_session(context)

        customer = generate_mobile_customer_data()
        customer_env = customer.as_maestro_env()
        self.run_flow(
            "common/create_customer_basic.yaml",
            extra_env=customer_env,
            step_title="Complete Basic customer page",
            expected="Locations form is displayed",
        )
        location_result = self.run_flow(
            "common/create_customer_locations.yaml",
            extra_env=customer_env,
            step_title="Complete Location page",
            expected="KTP document form is displayed",
        )
        customer_card_address = customer_card_address_from_maestro_result(location_result)
        self.run_flow(
            "common/create_customer_documents.yaml",
            extra_env=customer_env,
            step_title="Complete Documents page",
            expected="New Customer List page is displayed",
        )

        find_created_customer_card(
            customer,
            customer_card_address=customer_card_address,
            settings=self.settings,
            device=context.device,
        )
        self.run_flow(
            "validate_customer_list_card.yaml",
            extra_env={
                **customer_env,
                "EWORK_CUSTOMER_CARD_ADDRESS": customer_card_address,
            },
            step_title="Verify created customer card",
            expected="Name, address, and customer type match the submitted customer",
        )
        return customer
