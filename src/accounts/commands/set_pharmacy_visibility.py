from django.db import transaction

from accounts.models import User


@transaction.atomic
def set_pharmacy_visibility(user_id, *, visible):
    """Publishes or hides the pharmacy in search."""
    user = User.objects.select_related('pharmacy_account__pharmacy').get(pk=user_id)
    pharmacy = user.pharmacy_account.pharmacy
    pharmacy.set_visibility(visible)
    pharmacy.save(update_fields=['visible'])
