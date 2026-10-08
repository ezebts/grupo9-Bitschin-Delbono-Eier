from django.db import transaction

from accounts.models import ClientAccount, PharmacyAccount, User


@transaction.atomic
def signup(user: User, role: str):
    """Register the user and the account for their role."""
    user.role = role
    user.save(update_fields=['role'])

    if role == User.Role.CUSTOMER:
        ClientAccount.objects.create(
            user=user,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        return

    PharmacyAccount.objects.create(user=user)
