from django.db import transaction

from accounts.models import ClientAccount
from shared.values import Location


@transaction.atomic
def update_client_location(user_id, location: Location):
    """Saves the location the client searches pharmacies from."""

    client_account = ClientAccount.objects.get(user_id=user_id)
    client_account.update_search_preferences(location, client_account.search_radius)
    client_account.save()
