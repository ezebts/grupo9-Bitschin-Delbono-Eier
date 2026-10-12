from dataclasses import dataclass

from accounts.models import (
    Cuit,
    DeliveryTerms,
    OpeningHours,
    PreparationTag,
    User,
)
from shared.values import Location, PhoneNumber


@dataclass(frozen=True)
class PharmacyAccountProfile:
    first_name: str
    last_name: str
    email: str
    google_linked: bool
    visible: bool
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


def get_account_pharmacy_profile(user_id):
    """Gets the pharmacy profile data."""

    user = User.objects.select_related('pharmacy_account__pharmacy').get(pk=user_id)

    account, pharmacy = user.pharmacy_account, user.pharmacy_account.pharmacy

    return PharmacyAccountProfile(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        google_linked=user.socialaccount_set.filter(provider='google').exists(),
        visible=pharmacy.visible,
        kind=pharmacy.kind,
        trade_name=pharmacy.trade_name,
        legal_name=account.legal_name,
        cuit=account.cuit,
        technical_director=account.technical_director,
        license=account.license,
        request_email=pharmacy.request_email,
        phone=pharmacy.phone,
        website=pharmacy.website,
        location=pharmacy.location,
        opening_hours=pharmacy.opening_hours,
        delivery_terms=pharmacy.delivery_terms,
        preparation_tags=pharmacy.preparation_tags,
    )
