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

    user = User.objects.get(pk=user_id)

    return PharmacyAccountProfile(
        email=user.email,
        google_linked=user.socialaccount_set.filter(provider='google').exists(),
        visible=user.pharmacy_account.visible,
        kind=user.pharmacy_account.kind,
        trade_name=user.pharmacy_account.trade_name,
        legal_name=user.pharmacy_account.legal_name,
        cuit=user.pharmacy_account.cuit,
        technical_director=user.pharmacy_account.technical_director,
        license=user.pharmacy_account.license,
        request_email=user.pharmacy_account.request_email,
        phone=user.pharmacy_account.phone,
        website=user.pharmacy_account.website,
        location=user.pharmacy_account.location,
        opening_hours=user.pharmacy_account.opening_hours,
        delivery_terms=user.pharmacy_account.delivery_terms,
        preparation_tags=user.pharmacy_account.preparation_tags,
    )
