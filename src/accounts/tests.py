import pytest
from django.urls import reverse

from accounts.forms import SignupForm
from accounts.models import User

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
def test_email_signup_saves_selected_role(client, role):
    email_signup(client, role)

    assert User.objects.get(email='ana@example.com').role == role


def test_email_signup_requires_role(client):
    email_signup(client, '')

    assert not User.objects.exists()


def test_google_signup_saves_selected_role():
    user = User.objects.create_user(username='ana', email='ana@example.com')
    form = SignupForm(
        data={'role': User.Role.PHARMACY, 'first_name': 'Ana', 'last_name': 'Pérez'},
    )

    assert form.is_valid()
    form.signup(None, user)
    user.refresh_from_db()
    assert user.is_pharmacy
