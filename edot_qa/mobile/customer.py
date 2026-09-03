from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edot_qa.ai.test_data import GeneratedTestData, generate_test_data
from edot_qa.reporting.allure_helpers import attach_json


@dataclass(frozen=True)
class MobileCustomerData:
    name: str
    contact: str
    address: str
    run_id: str
    source: str

    @classmethod
    def from_generated_test_data(cls, generated: GeneratedTestData) -> "MobileCustomerData":
        customer = generated.data.customer
        return cls(
            name=customer.name,
            contact=customer.contact,
            address=customer.address,
            run_id=generated.run_id,
            source=generated.source,
        )

    def as_maestro_env(self) -> dict[str, str]:
        return {
            "EWORK_CUSTOMER_NAME": self.name,
            "EWORK_CUSTOMER_CONTACT": self.contact,
            "EWORK_CUSTOMER_ADDRESS": self.address,
        }

    def as_allure_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "contact": self.contact,
            "address": self.address,
            "run_id": self.run_id,
            "source": self.source,
        }


def generate_mobile_customer_data(run_id: str | None = None) -> MobileCustomerData:
    customer = MobileCustomerData.from_generated_test_data(generate_test_data(run_id=run_id))
    attach_json("mobile-customer-data", customer.as_allure_payload())
    return customer
