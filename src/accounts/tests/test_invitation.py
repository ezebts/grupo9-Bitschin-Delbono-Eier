from http import HTTPStatus

import pytest
from django.urls import reverse

from accounts.models import InvitationLink, Pharmacy, PharmacyAccount, User

pytestmark = pytest.mark.django_db


def test_invitation_link_round_trip_reuses_the_signed_value():
    link = InvitationLink(
        role=User.Role.PHARMACY,
        email='farmacia@example.com',
        next_url='/chats/?conversation_id=3',
        details={'pharmacy_id': 7},
    )

    value = str(link)

    assert str(link) == value
    restored = InvitationLink.from_value(value)
    assert restored.role == User.Role.PHARMACY
    assert restored.email == 'farmacia@example.com'
    assert restored.next_url == '/chats/?conversation_id=3'
    assert restored.details == {'pharmacy_id': 7}
    assert str(restored) == value


def test_invitation_signup_hides_role_and_joins_the_pharmacy(client):
    pharmacy = Pharmacy.objects.create(
        trade_name='Galénica',
        request_email='farmacia@example.com',
    )
    link = InvitationLink(
        role=User.Role.PHARMACY,
        email=pharmacy.request_email,
        next_url='/chats/',
        details={'pharmacy_id': pharmacy.pk},
    )

    page = client.get(str(link))

    assert page.status_code == HTTPStatus.OK
    html = page.content.decode()
    assert '¿Cómo vas a usar la app?' not in html
    assert 'Registrarte con Google' not in html
    assert 'name="role"' in html
    assert 'name="email"' in html
    assert 'farmacia@example.com' in html
    assert 'name="invitation_link"' in html
    assert 'name="password1"' in html
    assert 'name="next"' in html
    assert 'value="/chats/"' in html

    signed_up = client.post(
        reverse('account_signup'),
        {
            'role': User.Role.PHARMACY,
            'first_name': 'Ana',
            'last_name': 'Pérez',
            'email': pharmacy.request_email,
            'password1': 'una-clave-segura-123',
            'password2': 'una-clave-segura-123',
            'invitation_link': str(link),
            'next': '/chats/',
        },
    )

    assert signed_up.status_code == HTTPStatus.FOUND
    assert signed_up.url == '/chats/'
    user = User.objects.get(email=pharmacy.request_email)
    assert user.role == User.Role.PHARMACY
    assert user.pharmacy_account.pharmacy_id == pharmacy.pk
    assert Pharmacy.objects.count() == 1
    assert PharmacyAccount.objects.count() == 1


def test_invalid_invitation_opens_the_normal_signup(client):
    response = client.get(reverse('invitation'), {'_invitation': 'no-es-un-link'})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('account_signup')
