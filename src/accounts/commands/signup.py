from allauth.account.models import EmailAddress
from django.db import transaction

from accounts.exceptions import InvalidInvitationLinkError
from accounts.models import (
    ClientAccount,
    DeliveryTerms,
    InvitationLink,
    Pharmacy,
    PharmacyAccount,
    PreparationTag,
    User,
)


@transaction.atomic
def signup(user: User, role: str):
    """Register the user and the account for their role."""
    user.role = role
    user.save(update_fields=['role'])

    if role == User.Role.CUSTOMER:
        ClientAccount.objects.create(user=user)
        return

    pharmacy = Pharmacy.objects.create(request_email=user.email)
    pharmacy.update_delivery_terms(
        DeliveryTerms.create(pickup=True, home_delivery=False, base_cost=None)
    )
    pharmacy.update_preparation_tags(set(PreparationTag))
    pharmacy.save()

    PharmacyAccount.objects.create(user=user, pharmacy=pharmacy)


@transaction.atomic
def signup_with_invitation(invitation_link: InvitationLink) -> User:
    """Create the invited account with no usable password and a verified email."""

    user = User(
        username=invitation_link.email,
        email=invitation_link.email,
        first_name='',
        last_name='',
        role=invitation_link.role,
    )
    user.set_unusable_password()
    user.save()

    EmailAddress.objects.create(
        user=user,
        email=invitation_link.email.lower(),
        primary=True,
        verified=True,
    )

    if invitation_link.role == User.Role.CUSTOMER:
        ClientAccount.objects.create(user=user)

    elif invitation_link.role == User.Role.PHARMACY:
        pharmacy_id = invitation_link.details.get('pharmacy_id')

        if not pharmacy_id:
            pharmacy_id = Pharmacy.objects.create(request_email=user.email).id

        if PharmacyAccount.objects.filter(pharmacy_id=pharmacy_id).exists():
            raise InvalidInvitationLinkError

        PharmacyAccount.objects.create(user=user, pharmacy_id=pharmacy_id)

    else:
        raise InvalidInvitationLinkError

    return user
