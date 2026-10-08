from dataclasses import dataclass

from django.db import transaction

from accounts.models import (
    Cuit,
    DeliveryTerms,
    OpeningHours,
    PreparationTag,
    User,
)
from shared.values import Location, PhoneNumber


@dataclass(frozen=True)
class UpdatePharmacyProfileParams:
    visible: bool
    kind: str
    trade_name: str
    legal_name: str
    cuit: Cuit
    technical_director: str
    license: str
    request_email: str
    phone: PhoneNumber
    website: str
    location: Location
    opening_hours: OpeningHours
    delivery_terms: DeliveryTerms
    preparation_tags: set[PreparationTag]


@transaction.atomic
def update_pharmacy_profile(user_id, params: UpdatePharmacyProfileParams):
    """Updates the pharmacy profile data."""

    user = User.objects.get(pk=user_id)

    user.pharmacy_account.update_establishment(
        params.visible,
        params.kind,
        params.trade_name,
        params.legal_name,
        params.cuit,
        params.technical_director,
        params.license,
    )

    user.pharmacy_account.update_contact(
        params.request_email,
        params.phone,
        params.website,
    )

    user.pharmacy_account.update_location(params.location)
    user.pharmacy_account.update_opening_hours(params.opening_hours)
    user.pharmacy_account.update_delivery_terms(params.delivery_terms)
    user.pharmacy_account.update_preparation_tags(params.preparation_tags)
    user.pharmacy_account.save()
