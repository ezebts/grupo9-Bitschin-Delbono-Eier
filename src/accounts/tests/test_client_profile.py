from dataclasses import replace

import pytest

from accounts.commands.update_client_profile import (
    UpdateClientProfileParams,
    update_client_profile,
)
from accounts.models import ClientAccount, MailPreferences, SearchRadius, User
from shared.values import Location, PhoneNumber

pytestmark = pytest.mark.django_db


@pytest.fixture(scope='module')
def client_profile_params():
    return UpdateClientProfileParams(
        first_name='Lucía',
        last_name='Fernández',
        phone=PhoneNumber.AR('11 5555-4444'),
        location=Location.create('Av. Santa Fe 3820', 'Palermo', '1425'),
        search_radius=SearchRadius.KM3,
        health_insurance_number='OSDE 123',
        mail_preferences=MailPreferences(
            on_reply=True,
            on_status_change=False,
            on_quote_expiry=False,
        ),
    )


@pytest.fixture
def client_account(db):  # noqa: ARG001
    user = User(
        username='ana@example.com',
        email='ana@example.com',
        role=User.Role.CUSTOMER,
        first_name='Ana',
        last_name='Pérez',
    )
    user.set_unusable_password()
    user.save()
    return ClientAccount.objects.create(
        user=user,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def test_client_updates_profile(client_account, client_profile_params):
    update_client_profile(client_account.user_id, client_profile_params)

    client_account.refresh_from_db()
    user = client_account.user
    user.refresh_from_db()

    assert client_account.first_name == client_profile_params.first_name
    assert client_account.last_name == client_profile_params.last_name
    assert client_account.phone == client_profile_params.phone
    assert (
        client_account.health_insurance_number
        == client_profile_params.health_insurance_number
    )

    assert client_account.location == client_profile_params.location
    assert client_account.search_radius == client_profile_params.search_radius

    assert client_account.mail_preferences == client_profile_params.mail_preferences

    assert user.first_name == client_profile_params.first_name
    assert user.last_name == client_profile_params.last_name


def test_client_clears_health_insurance(client_account, client_profile_params):
    update_client_profile(client_account.user_id, client_profile_params)
    update_client_profile(
        client_account.user_id,
        replace(client_profile_params, health_insurance_number=''),
    )

    client_account.refresh_from_db()
    assert client_account.health_insurance_number == ''
