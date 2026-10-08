import pytest
from django.urls import reverse

from accounts.models import ClientAccount, PharmacyAccount, User

pytestmark = pytest.mark.django_db


def email_signup(client, role):
    return client.post(
        reverse('account_signup'),
        {
            'role': role,
            'first_name': 'Ana',
            'last_name': 'Pérez',
            'email': 'ana@example.com',
            'password1': 'una-clave-segura-123',
            'password2': 'una-clave-segura-123',
        },
    )


@pytest.mark.parametrize('role', User.Role.values)
def test_email_signup_opens_an_account_for_the_selected_role(client, role):
    email_signup(client, role)

    user = User.objects.get(email='ana@example.com')
    assert user.role == role
    if role == User.Role.CUSTOMER:
        assert user.client_account.first_name == 'Ana'
        assert user.client_account.last_name == 'Pérez'
        assert not PharmacyAccount.objects.exists()
        return
    assert user.pharmacy_account.pk
    assert not ClientAccount.objects.exists()


def test_email_signup_requires_role(client):
    email_signup(client, '')

    assert not User.objects.exists()
