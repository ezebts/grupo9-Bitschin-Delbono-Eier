from dataclasses import dataclass

from django.db import transaction

from accounts.models import MailPreferences, User
from shared.values import Location, PhoneNumber


@dataclass(frozen=True)
class UpdateClientProfileParams:
    first_name: str
    last_name: str
    phone: PhoneNumber
    location: Location
    search_radius: int
    health_insurance_number: str
    mail_preferences: MailPreferences


@transaction.atomic
def update_client_profile(user_id, params: UpdateClientProfileParams):
    """Updates the client profile data."""

    user = User.objects.get(pk=user_id)

    user.first_name = params.first_name
    user.last_name = params.last_name

    user.client_account.update_personal_details(
        params.first_name,
        params.last_name,
        params.phone,
        params.health_insurance_number,
    )

    user.client_account.update_search_preferences(
        params.location,
        params.search_radius,
    )

    user.client_account.update_mail_preferences(params.mail_preferences)
    user.client_account.save()
    user.save(update_fields=['first_name', 'last_name'])
