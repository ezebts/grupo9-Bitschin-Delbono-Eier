from django.db import transaction

from accounts.commands.signup import signup_with_invitation
from accounts.models import InvitationLink, User


@transaction.atomic
def create_account_from_invitation(invitation_link: InvitationLink) -> User:
    """Create an account for the invitation email with no usable password."""

    user = User(
        username=invitation_link.email,
        email=invitation_link.email,
        first_name='',
        last_name='',
    )
    user.set_unusable_password()
    user.save()

    signup_with_invitation(user, invitation_link)

    return user
