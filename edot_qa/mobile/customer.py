from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from edot_qa.ai.test_data import GeneratedTestData, generate_test_data
from edot_qa.reporting.allure_helpers import allure_step, attach_json


@dataclass(frozen=True)
class MobileCustomerData:
    name: str
    contact: str
    address: str
    ktp_number: str
    run_id: str
    source: str

    @classmethod
    def from_generated_test_data(cls, generated: GeneratedTestData) -> "MobileCustomerData":
        customer = generated.data.customer
        return cls(
            name=customer.name,
            contact=customer.contact,
            address=customer.address,
            ktp_number=_fake_ktp_number(generated.run_id),
            run_id=generated.run_id,
            source=generated.source,
        )

    def as_maestro_env(self) -> dict[str, str]:
        return {
            "EWORK_CUSTOMER_NAME": self.name,
            "EWORK_CUSTOMER_CONTACT": self.contact,
            "EWORK_CUSTOMER_CONTACT_PERSON": self.name,
            "EWORK_CUSTOMER_ADDRESS": self.address,
            "EWORK_CUSTOMER_KTP_NUMBER": self.ktp_number,
        }

    def as_allure_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "contact": self.contact,
            "address": self.address,
            "ktp_number": self.ktp_number,
            "run_id": self.run_id,
            "source": self.source,
        }


def generate_mobile_customer_data(run_id: str | None = None) -> MobileCustomerData:
    with allure_step("Generate mobile customer data", data={"run_id": run_id or "<auto>"}, screenshot=False):
        customer = MobileCustomerData.from_generated_test_data(generate_test_data(run_id=run_id))
        attach_json("mobile-customer-data", customer.as_allure_payload())
        return customer


def _fake_ktp_number(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    suffix = int(digest[:16], 16) % 10**14
    return f"31{suffix:014d}"
