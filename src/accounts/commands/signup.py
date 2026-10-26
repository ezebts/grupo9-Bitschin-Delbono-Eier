from allauth.account.models import EmailAddress
from django.db import transaction

from accounts.commands.register_device_key import (
    RegisterDeviceKeyParams,
    register_device_key,
)
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
def signup(user: User, role: str, public_key: str = ''):
    """Register the user, the account for their role and their device key."""
    user.role = role
    user.save(update_fields=['role'])

    if public_key:
        register_device_key(user.id, RegisterDeviceKeyParams(public_key))

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
def signup_with_invitation(  # noqa: C901
    invitation_link: InvitationLink,
    public_key: str = '',
) -> User:
    """Open the invited account, or attach a free pharmacy to an existing user."""

    user = User.objects.filter(email__iexact=invitation_link.email).first()

    user_was_already_registered = user is not None

    if not user_was_already_registered:
        user = User(
            username=invitation_link.email,
            email=invitation_link.email,
            first_name='',
            last_name='',
            role=invitation_link.role,
        )
        user.set_unusable_password()
        user.save()

    user_has_email_address = EmailAddress.objects.filter(
        user=user,
        email__iexact=invitation_link.email,
    ).exists()

    if not user_has_email_address:
        EmailAddress.objects.create(
            user=user,
            email=invitation_link.email.lower(),
            primary=not EmailAddress.objects.filter(user=user, primary=True).exists(),
            verified=True,
        )

    if public_key:
        register_device_key(user.id, RegisterDeviceKeyParams(public_key))

    if invitation_link.role == User.Role.CUSTOMER:
        if not user_was_already_registered:
            ClientAccount.objects.create(user=user)
        return user

    if invitation_link.role != User.Role.PHARMACY:
        raise InvalidInvitationLinkError

    pharmacy_id = invitation_link.details.get('pharmacy_id')
    if not pharmacy_id:
        raise InvalidInvitationLinkError

    if not user.is_pharmacy or PharmacyAccount.objects.filter(user=user).exists():
        return user

    if PharmacyAccount.objects.filter(pharmacy_id=pharmacy_id).exists():
        if not user_was_already_registered:
            raise InvalidInvitationLinkError
        return user

    PharmacyAccount.objects.create(user=user, pharmacy_id=pharmacy_id)

    return user
