from dataclasses import dataclass

from django.db import transaction

from accounts.models import (
    Cuit,
    DeliveryTerms,
    OpeningHours,
    PharmacyMailPreferences,
    PreparationTag,
    User,
)
from shared.values import Location, PhoneNumber


@dataclass(frozen=True)
class UpdatePharmacyProfileParams:
    first_name: str
    last_name: str
    kind: str
    trade_name: str
    legal_name: str
    cuit: Cuit | None
    technical_director: str
    license: str
    request_email: str
    phone: PhoneNumber | None
    website: str
    location: Location | None
    opening_hours: OpeningHours | None
    delivery_terms: DeliveryTerms | None
    preparation_tags: set[PreparationTag]
    mail_preferences: PharmacyMailPreferences


@transaction.atomic
def update_pharmacy_profile(user_id, params: UpdatePharmacyProfileParams):
    """Updates the pharmacy profile data."""

    user = User.objects.select_related('pharmacy_account__pharmacy').get(pk=user_id)

    account, pharmacy = user.pharmacy_account, user.pharmacy_account.pharmacy

    user.first_name = params.first_name
    user.last_name = params.last_name

    pharmacy.update_establishment(params.kind, params.trade_name)
    pharmacy.update_contact_info(params.request_email, params.phone, params.website)
    pharmacy.update_location(params.location)
    pharmacy.update_opening_hours(params.opening_hours)
    pharmacy.update_delivery_terms(params.delivery_terms)
    pharmacy.update_preparation_tags(params.preparation_tags)
    pharmacy.update_mail_preferences(params.mail_preferences)

    account.update_legal_info(
        params.legal_name,
        params.cuit,
        params.technical_director,
        params.license,
    )

    pharmacy.save()
    account.save()
    user.save(update_fields=['first_name', 'last_name'])
