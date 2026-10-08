from dataclasses import dataclass

from accounts.models import MailPreferences, User
from shared.values import Location, PhoneNumber


@dataclass(frozen=True)
class ClientAccountProfile:
    email: str
    google_linked: bool
    first_name: str
    last_name: str
    phone: PhoneNumber | None
    health_insurance_number: str
    location: Location | None
    search_radius: int | None
    mail_preferences: MailPreferences | None


def get_account_client_profile(user_id):
    """Gets the client profile data."""

    user = User.objects.get(pk=user_id)

    return ClientAccountProfile(
        email=user.email,
        google_linked=user.socialaccount_set.filter(provider='google').exists(),
        first_name=user.client_account.first_name,
        last_name=user.client_account.last_name,
        phone=user.client_account.phone,
        health_insurance_number=user.client_account.health_insurance_number,
        location=user.client_account.location,
        search_radius=user.client_account.search_radius,
        mail_preferences=user.client_account.mail_preferences,
    )
