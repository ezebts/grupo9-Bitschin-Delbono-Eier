import pytest
from django.urls import reverse

from accounts.commands.register_device_key import (
    RegisterDeviceKeyParams,
    register_device_key,
)
from accounts.models import (
    ClientAccount,
    Pharmacy,
    PharmacyAccount,
    PreparationTag,
    User,
)
from shared.tests.encryption import generate_device_public_key

pytestmark = pytest.mark.django_db


@pytest.fixture(scope='module')
def device_public_key():
    return generate_device_public_key()


def email_signup(client, role, public_key=''):
    return client.post(
        reverse('account_signup'),
        {
            'role': role,
            'first_name': 'Ana',
            'last_name': 'Pérez',
            'email': 'ana@example.com',
            'password1': 'una-clave-segura-123',
            'password2': 'una-clave-segura-123',
            'public_key': public_key,
        },
    )


@pytest.mark.parametrize('role', User.Role.values)
def test_email_signup_opens_an_account_for_the_selected_role(
    client,
    role,
    device_public_key,
):
    public_key, fingerprint = device_public_key

    email_signup(client, role, public_key)

    user = User.objects.get(email='ana@example.com')
    assert user.device_keys.get().fingerprint == fingerprint
    assert user.role == role
    assert user.first_name == 'Ana'
    assert user.last_name == 'Pérez'
    assert user.get_initials() == 'AP'
    if role == User.Role.CUSTOMER:
        assert user.client_account.pk
        assert not PharmacyAccount.objects.exists()
        assert not Pharmacy.objects.exists()
        return
    pharmacy = user.pharmacy_account.pharmacy
    assert pharmacy.request_email == user.email
    assert not pharmacy.visible
    assert pharmacy.delivery_terms.pickup
    assert pharmacy.preparation_tags == set(PreparationTag)
    assert not ClientAccount.objects.exists()


def test_email_signup_requires_role(client):
    email_signup(client, '')

    assert not User.objects.exists()


def test_email_signup_ignores_a_device_key_of_another_account(
    client,
    device_public_key,
):
    public_key, fingerprint = device_public_key
    other = User.objects.create_user(username='otra@example.com')
    register_device_key(other.id, RegisterDeviceKeyParams(public_key))

    email_signup(client, User.Role.CUSTOMER, public_key)

    user = User.objects.get(email='ana@example.com')
    assert user.client_account.pk
    assert not user.device_keys.exists()
    assert other.device_keys.get().fingerprint == fingerprint
