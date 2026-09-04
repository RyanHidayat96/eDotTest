from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from edot_qa.ai.test_data import GeneratedTestData, generate_test_data
from edot_qa.reporting.allure_helpers import allure_step, attach_json


MOBILE_PHONE_RE = re.compile(r"^\+62\d{8,13}$")


@dataclass(frozen=True)
class MobileCustomerData:
    name: str
    contact: str
    contact_person: str
    address: str
    ktp_number: str
    run_id: str
    source: str

    @classmethod
    def from_generated_test_data(cls, generated: GeneratedTestData) -> "MobileCustomerData":
        customer = generated.data.customer
        name = _unique_customer_name(customer.name, generated.run_id)
        return cls(
            name=name,
            contact=_mobile_phone_contact(customer.contact, generated.run_id),
            contact_person=_unique_contact_person_name(generated.run_id),
            address=customer.address,
            ktp_number=_fake_ktp_number(generated.run_id),
            run_id=generated.run_id,
            source=generated.source,
        )

    def as_maestro_env(self) -> dict[str, str]:
        return {
            "EWORK_CUSTOMER_NAME": self.name,
            "EWORK_CUSTOMER_CONTACT": _mobile_phone_input(self.contact),
            "EWORK_CUSTOMER_CONTACT_PERSON": self.contact_person,
            "EWORK_CUSTOMER_KTP_NUMBER": self.ktp_number,
        }

    def as_allure_payload(self) -> dict[str, Any]:
        return {
            "generated_customer": {
                "name": self.name,
                "contact": self.contact,
                "address": self.address,
            },
            "submitted_customer": {
                "name": self.name,
                "contact": self.contact,
                "contact_person": self.contact_person,
            },
            "mobile_address_mapping": {
                "generated_address_directly_entered": False,
                "persisted_address_source": "current-location address field",
            },
            "ktp_number": self.ktp_number,
            "run_id": self.run_id,
            "source": self.source,
        }

    def as_persistence_payload(self, persisted_address: str) -> dict[str, Any]:
        return {
            "generated_customer": {
                "name": self.name,
                "contact": self.contact,
                "address": self.address,
            },
            "persisted_customer": {
                "name": self.name,
                "contact": self.contact,
                "address": persisted_address,
                "address_source": "current-location address field",
            },
            "address_mapping": {
                "generated_address_directly_entered": False,
                "generated_address_equals_persisted_address": _normalize_text(self.address)
                == _normalize_text(persisted_address),
                "verification_rule": (
                    "Tier 2 mobile address assertion uses the address captured from the app "
                    "after current-location selection."
                ),
            },
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
    suffix = int(digest[:8], 16) % 10**4
    return f"317507010190{suffix:04d}"


def _mobile_phone_contact(contact: str, run_id: str) -> str:
    if MOBILE_PHONE_RE.match(contact):
        return contact
    digest = hashlib.sha256(f"{run_id}:contact".encode("utf-8")).hexdigest()
    suffix = int(digest[:8], 16) % 10**9
    return f"+628{suffix:09d}"


def _mobile_phone_input(contact: str) -> str:
    if contact.startswith("+62"):
        return contact[3:]
    return contact


def _unique_customer_name(name: str, run_id: str) -> str:
    suffix = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8].upper()
    if suffix in name:
        return name
    marker = f" QA {suffix}"
    return f"{name[:100 - len(marker)].rstrip()}{marker}"


def _unique_contact_person_name(run_id: str) -> str:
    digest = hashlib.sha256(f"{run_id}:contact-person".encode("utf-8")).hexdigest()
    names = ("Raka", "Dina", "Arif", "Sinta", "Bima", "Nadia")
    name = names[int(digest[:2], 16) % len(names)]
    suffix = digest[2:8].upper()
    return f"{name} QA PIC {suffix}"


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()
