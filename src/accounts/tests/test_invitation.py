from http import HTTPStatus
from urllib.parse import parse_qs, urlencode

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.commands.signup import signup_with_invitation
from accounts.exceptions import InvalidInvitationLinkError
from accounts.models import (
    ClientAccount,
    InvitationLink,
    Pharmacy,
    PharmacyAccount,
    User,
)
from accounts.views import InvitationSignupView

pytestmark = pytest.mark.django_db

PASSWORD = 'una-clave-segura-123'  # noqa: S105


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


def test_signup_with_invitation_opens_a_client_account_without_password():
    link = InvitationLink(
        role=User.Role.CUSTOMER,
        email='cliente@example.com',
        next_url='/orders/',
    )

    user = signup_with_invitation(link)

    assert user.email == 'cliente@example.com'
    assert user.first_name == ''
    assert user.last_name == ''
    assert user.role == User.Role.CUSTOMER
    assert not user.has_usable_password()
    assert user.client_account.pk
    assert not PharmacyAccount.objects.exists()
    email_address = EmailAddress.objects.get(user=user, email='cliente@example.com')
    assert email_address.primary
    assert email_address.verified


def test_signup_with_invitation_joins_the_invited_pharmacy():
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

    user = signup_with_invitation(link)

    assert user.role == User.Role.PHARMACY
    assert not user.has_usable_password()
    assert user.pharmacy_account.pharmacy_id == pharmacy.pk
    assert not ClientAccount.objects.exists()
    assert Pharmacy.objects.count() == 1


def test_signup_with_invitation_rejects_a_pharmacy_link_without_a_pharmacy():
    link = InvitationLink(
        role=User.Role.PHARMACY,
        email='farmacia@example.com',
        next_url='/chats/',
    )

    with pytest.raises(InvalidInvitationLinkError):
        signup_with_invitation(link)

    assert not User.objects.exists()
    assert not Pharmacy.objects.exists()


def test_signup_with_invitation_joins_an_existing_pharmacy_user():
    pharmacy = Pharmacy.objects.create(
        trade_name='Galénica',
        request_email='farmacia@example.com',
    )
    User.objects.create_user(
        username=pharmacy.request_email,
        email=pharmacy.request_email,
        password=PASSWORD,
        role=User.Role.PHARMACY,
    )
    link = InvitationLink(
        role=User.Role.PHARMACY,
        email=pharmacy.request_email,
        next_url='/chats/',
        details={'pharmacy_id': pharmacy.pk},
    )

    user = signup_with_invitation(link)
    again = signup_with_invitation(link)

    assert again.pk == user.pk
    assert User.objects.count() == 1
    assert user.pharmacy_account.pharmacy_id == pharmacy.pk
    assert PharmacyAccount.objects.count() == 1


def test_signup_with_invitation_leaves_an_existing_customer_unchanged():
    user = User.objects.create_user(
        username='ana@example.com',
        email='ana@example.com',
        password=PASSWORD,
        role=User.Role.CUSTOMER,
    )
    ClientAccount.objects.create(user=user)
    pharmacy = Pharmacy.objects.create(
        trade_name='Galénica',
        request_email=user.email,
    )
    link = InvitationLink(
        role=User.Role.PHARMACY,
        email=user.email,
        next_url='/chats/',
        details={'pharmacy_id': pharmacy.pk},
    )

    signup_with_invitation(link)

    user.refresh_from_db()
    assert user.role == User.Role.CUSTOMER
    assert not PharmacyAccount.objects.exists()


@pytest.mark.parametrize(
    ('has_password', 'has_google', 'expected'),
    [(False, False, False), (True, False, True), (False, True, True)],
)
def test_account_is_complete(has_password, has_google, expected):
    user = User.objects.create_user(
        username='ana@example.com',
        email='ana@example.com',
        password=PASSWORD if has_password else None,
    )
    if has_google:
        SocialAccount.objects.create(user=user, provider='google', uid='google-uid')

    assert InvitationSignupView._account_is_complete(user) is expected  # noqa: SLF001


def test_invitation_opens_the_confirmation_screen(client):
    link = InvitationLink(
        role=User.Role.CUSTOMER,
        email='cliente@example.com',
        next_url='/orders/',
    )

    page = client.get(str(link))

    assert page.status_code == HTTPStatus.OK
    html = page.content.decode()
    assert 'cliente@example.com' in html
    assert 'name="password1"' not in html
    assert 'name="first_name"' not in html


def test_invitation_primera_vez_post_crea_cuenta_y_loguea(client):
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

    signed_up = client.post(str(link))

    assert signed_up.status_code == HTTPStatus.FOUND
    assert signed_up.url == '/chats/'
    user = User.objects.get(email=pharmacy.request_email)
    assert user.role == User.Role.PHARMACY
    assert not user.has_usable_password()
    assert user.pharmacy_account.pharmacy_id == pharmacy.pk
    assert client.session['_auth_user_id'] == str(user.pk)


def test_invitation_autenticado_redirige_directo(client):
    user = User.objects.create_user(
        username='ana@example.com',
        email='ana@example.com',
        password=PASSWORD,
    )
    link = InvitationLink(
        role=User.Role.CUSTOMER,
        email='ana@example.com',
        next_url='/orders/',
    )
    client.force_login(user)

    response = client.get(str(link))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == '/orders/'


def test_invitation_cuenta_sin_credenciales_muestra_completar_cuenta(client):
    User.objects.create_user(
        username='ana@example.com',
        email='ana@example.com',
        password=None,
    )
    link = InvitationLink(
        role=User.Role.CUSTOMER,
        email='ana@example.com',
        next_url='/orders/',
    )

    page = client.get(str(link))

    assert page.status_code == HTTPStatus.OK
    html = page.content.decode()
    assert 'ana@example.com' in html
    assert 'name="password1"' in html
    assert 'name="password2"' in html
    assert 'Continuar con Google' in html
    assert urlencode({'next': '/orders/'}) in html


def test_invitation_cuenta_sin_credenciales_establece_password(client):
    user = User.objects.create_user(
        username='ana@example.com',
        email='ana@example.com',
        password=None,
    )
    link = InvitationLink(
        role=User.Role.CUSTOMER,
        email='ana@example.com',
        next_url='/orders/',
    )

    response = client.post(str(link), {'password1': PASSWORD, 'password2': PASSWORD})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == '/orders/'
    user.refresh_from_db()
    assert user.has_usable_password()
    assert user.check_password(PASSWORD)
    assert client.session['_auth_user_id'] == str(user.pk)


@pytest.mark.parametrize('with_google', [False, True])
def test_invitation_cuenta_completa_redirige_a_login(client, with_google):
    user = User.objects.create_user(
        username='ana@example.com',
        email='ana@example.com',
        password=None if with_google else PASSWORD,
    )
    if with_google:
        SocialAccount.objects.create(user=user, provider='google', uid='google-uid')
    link = InvitationLink(
        role=User.Role.CUSTOMER,
        email='ana@example.com',
        next_url='/orders/',
    )

    response = client.get(str(link))

    assert response.status_code == HTTPStatus.FOUND
    login_url, _, query = response.url.partition('?')
    assert login_url == reverse('account_login')
    assert parse_qs(query) == {'next': ['/orders/']}
    assert 'Iniciá sesión para continuar.' in [
        message.message for message in get_messages(response.wsgi_request)
    ]


def test_invalid_invitation_opens_the_normal_signup(client):
    response = client.get(reverse('invitation'), {'_invitation': 'no-es-un-link'})

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('account_signup')
