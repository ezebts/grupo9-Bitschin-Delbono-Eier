import pytest
from allauth.socialaccount.models import SocialAccount

from accounts.models import ClientAccount, PharmacyAccount, User
from accounts.queries.client_profile import get_account_client_profile
from accounts.queries.pharmacy_profile import get_account_pharmacy_profile

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):  # noqa: ARG001
    account = User(
        username='ana@example.com',
        email='ana@example.com',
        role=User.Role.CUSTOMER,
    )
    account.set_unusable_password()
    account.save()
    return account


def test_client_profile_includes_the_account_and_a_google_link(user):
    user.first_name = 'Ana'
    user.last_name = 'Pérez'
    user.save(update_fields=['first_name', 'last_name'])
    ClientAccount.objects.create(user=user)
    SocialAccount.objects.create(user=user, provider='google', uid='google-ana')

    profile = get_account_client_profile(user.id)

    assert profile.email == 'ana@example.com'
    assert profile.first_name == 'Ana'
    assert profile.last_name == 'Pérez'
    assert profile.google_linked


def test_pharmacy_profile_is_not_linked_when_google_is_missing(user):
    user.role = User.Role.PHARMACY
    user.save(update_fields=['role'])
    PharmacyAccount.objects.create(user=user, trade_name='Farmacia Galénica')

    profile = get_account_pharmacy_profile(user.id)

    assert profile.email == 'ana@example.com'
    assert profile.trade_name == 'Farmacia Galénica'
    assert not profile.google_linked
