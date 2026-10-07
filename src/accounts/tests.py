"""Tests for accounts: user model, signup, login, Google login, pages and admin."""

from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.urls import reverse

from accounts.forms import SignupForm
from accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = 'una-clave-segura-123'  # noqa: S105 (test-only password)
PASSWORD_FIELDS = ('password1', 'password2')
GOOGLE_CALLBACK_URL = '/accounts/google/login/callback/'
VALID_ROLE_FORM = {
    'role': User.Role.CUSTOMER,
    'first_name': 'Ana',
    'last_name': 'Pérez',
}


# Fixtures and helpers


@pytest.fixture(autouse=True)
def _clear_cache():
    # allauth keeps its rate limits (failed logins, signups) in the cache.
    cache.clear()


@pytest.fixture
def password():
    return PASSWORD


@pytest.fixture
def make_user():
    def _make_user(**kwargs):
        data = {
            'username': 'ana',
            'email': 'ana@example.com',
            'password': PASSWORD,
            **kwargs,
        }
        return User.objects.create_user(**data)

    return _make_user


@pytest.fixture
def signup_data():
    return {
        'role': User.Role.PHARMACY,
        'first_name': 'Ana',
        'last_name': 'Pérez',
        'email': 'ana@example.com',
        'password1': PASSWORD,
        'password2': PASSWORD,
    }


@pytest.fixture
def is_logged_in():
    def _is_logged_in(client):
        return '_auth_user_id' in client.session

    return _is_logged_in


@pytest.fixture
def google_app(settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        'google': {'APP': {'client_id': 'test-client-id', 'secret': 'test-secret'}},
    }
    return settings.SOCIALACCOUNT_PROVIDERS


@pytest.fixture
def google_query(client, google_app):
    # What our "Continuar con Google" button sends the browser to.
    assert google_app['google']['APP']['client_id']
    response = client.post(reverse('google_login'))
    return parse_qs(urlparse(response.url).query)


@pytest.fixture
def admin_client_with_users(client, make_user, password):
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password=password,
    )
    make_user(username='ana', email='ana@example.com')
    make_user(username='farm', email='farm@example.com', role=User.Role.PHARMACY)
    client.force_login(admin)
    return client


def signup(client, data):
    return client.post(reverse('account_signup'), data)


def login(client, email, password, **extra):
    return client.post(
        reverse('account_login'),
        {'login': email, 'password': password, **extra},
    )


def page_content(client, url_name):
    return client.get(reverse(url_name)).content.decode()


# User model


def test_new_user_is_customer_by_default(make_user):
    assert make_user().role == User.Role.CUSTOMER


@pytest.mark.parametrize(
    ('role', 'customer', 'pharmacy'),
    [(User.Role.CUSTOMER, True, False), (User.Role.PHARMACY, False, True)],
)
def test_role_helpers(make_user, role, customer, pharmacy):
    user = make_user(role=role)

    assert user.is_customer is customer
    assert user.is_pharmacy is pharmacy


def test_role_values_are_stable():
    # These values are stored in the database: changing them needs a migration.
    assert User.Role.values == ['customer', 'pharmacy']


@pytest.mark.parametrize(
    ('role', 'label'),
    [(User.Role.CUSTOMER, 'Cliente'), (User.Role.PHARMACY, 'Farmacia o laboratorio')],
)
def test_role_display_label(make_user, role, label):
    assert make_user(role=role).get_role_display() == label


def test_project_uses_custom_user_model():
    assert get_user_model() is User


@pytest.mark.parametrize(
    ('table', 'exists'),
    [('accounts_user', True), ('auth_user', False)],
)
def test_user_table(table, exists):
    assert (table in connection.introspection.table_names()) is exists


# Role form (asked on every signup, by email or by Google)


@pytest.mark.parametrize('role', User.Role.values)
def test_role_form_accepts_each_role(role):
    assert SignupForm(data={**VALID_ROLE_FORM, 'role': role}).is_valid()


@pytest.mark.parametrize('role', ['', 'admin', 'CUSTOMER'])
def test_role_form_rejects_invalid_role(role):
    form = SignupForm(data={**VALID_ROLE_FORM, 'role': role})

    assert not form.is_valid()
    assert 'role' in form.errors


@pytest.mark.parametrize('field', ['first_name', 'last_name'])
def test_role_form_requires_names(field):
    form = SignupForm(data={**VALID_ROLE_FORM, field: ''})

    assert not form.is_valid()
    assert field in form.errors


def test_role_form_uses_radio_buttons():
    assert isinstance(SignupForm().fields['role'].widget, forms.RadioSelect)


@pytest.mark.parametrize(
    ('field', 'label'),
    [
        ('role', '¿Cómo vas a usar la app?'),
        ('first_name', 'Nombre'),
        ('last_name', 'Apellido'),
    ],
)
def test_role_form_labels_in_spanish(field, label):
    assert SignupForm().fields[field].label == label


def test_role_form_signup_only_changes_role(make_user):
    # allauth calls signup() after saving the user (email or Google signup):
    # names are already saved by allauth, so it must only set the role.
    user = make_user(first_name='Original')
    form = SignupForm(
        data={**VALID_ROLE_FORM, 'role': User.Role.PHARMACY, 'first_name': 'Otro'},
    )

    assert form.is_valid()
    form.signup(None, user)
    user.refresh_from_db()
    assert user.is_pharmacy
    assert user.first_name == 'Original'


# Email signup


@pytest.mark.parametrize(
    'field',
    ['role', 'first_name', 'last_name', 'email', 'password1', 'password2'],
)
def test_signup_page_has_field(client, field):
    assert f'name="{field}"' in page_content(client, 'account_signup')


def test_signup_page_shows_both_roles(client):
    content = page_content(client, 'account_signup')

    assert 'Cliente' in content
    assert 'Farmacia o laboratorio' in content


@pytest.mark.parametrize('role', User.Role.values)
def test_signup_saves_each_role(client, signup_data, role):
    signup(client, {**signup_data, 'role': role})

    assert User.objects.get(email='ana@example.com').role == role


def test_signup_saves_names(client, signup_data):
    signup(client, signup_data)

    user = User.objects.get(email='ana@example.com')
    assert (user.first_name, user.last_name) == ('Ana', 'Pérez')


def test_signup_creates_primary_email(client, signup_data):
    signup(client, signup_data)

    assert EmailAddress.objects.get(email='ana@example.com').primary


def test_signup_logs_in_and_redirects_home(client, signup_data, is_logged_in):
    response = signup(client, signup_data)

    assert response.url == reverse('home')
    assert is_logged_in(client)


@pytest.mark.parametrize(
    'field',
    ['role', 'first_name', 'last_name', 'email', 'password1', 'password2'],
)
def test_signup_requires_field(client, signup_data, field):
    response = signup(client, {**signup_data, field: ''})

    assert response.status_code == HTTPStatus.OK
    assert not User.objects.exists()


@pytest.mark.parametrize('email', ['no-es-un-email', 'ana@'])
def test_signup_rejects_invalid_email(client, signup_data, email):
    signup(client, {**signup_data, 'email': email})

    assert not User.objects.exists()


@pytest.mark.parametrize('weak_password', ['12345678', 'abc'])
def test_signup_rejects_weak_password(client, signup_data, weak_password):
    signup(
        client,
        {**signup_data, 'password1': weak_password, 'password2': weak_password},
    )

    assert not User.objects.exists()


def test_signup_rejects_mismatched_passwords(client, signup_data):
    signup(client, {**signup_data, 'password2': 'otra-clave-distinta-456'})

    assert not User.objects.exists()


def test_signup_email_is_unique_ignoring_case(client, signup_data, make_user):
    make_user()

    signup(client, {**signup_data, 'email': 'ANA@EXAMPLE.COM'})

    assert User.objects.filter(email__iexact='ana@example.com').count() == 1


def test_signup_generates_unique_usernames(client, signup_data):
    # Users log in by email; allauth fills the required username by itself.
    emails = ['ana@example.com', 'ana.otra@example.com']
    for http_client, email in zip([client, Client()], emails, strict=True):
        signup(http_client, {**signup_data, 'email': email})

    usernames = set(User.objects.values_list('username', flat=True))
    assert len(usernames) == len(emails)
    assert '' not in usernames


def test_logged_in_user_skips_signup_page(client, make_user):
    client.force_login(make_user())

    response = client.get(reverse('account_signup'))

    assert response.url == reverse('home')


# Login


def test_login_page_offers_google(client):
    assert reverse('google_login') in page_content(client, 'account_login')


@pytest.mark.parametrize('field', ['login', 'password', 'remember'])
def test_login_page_has_field(client, field):
    assert f'name="{field}"' in page_content(client, 'account_login')


def test_login_page_links_to_password_reset(client):
    content = page_content(client, 'account_login')

    assert reverse('account_reset_password') in content


def test_login_redirects_home(client, make_user, password, is_logged_in):
    make_user()

    response = login(client, 'ana@example.com', password)

    assert response.url == reverse('home')
    assert is_logged_in(client)


def test_login_email_ignores_case(client, make_user, password, is_logged_in):
    make_user()

    login(client, 'ANA@EXAMPLE.COM', password)

    assert is_logged_in(client)


def test_login_wrong_password_fails(client, make_user, is_logged_in):
    make_user()

    response = login(client, 'ana@example.com', 'otra-clave-cualquiera')

    assert response.status_code == HTTPStatus.OK
    assert not is_logged_in(client)


def test_login_unknown_email_fails(client, make_user, password, is_logged_in):
    make_user()

    login(client, 'nadie@example.com', password)

    assert not is_logged_in(client)


@pytest.mark.parametrize('field', ['login', 'password'])
def test_login_requires_field(client, make_user, password, is_logged_in, field):
    make_user()
    data = {'login': 'ana@example.com', 'password': password, field: ''}

    response = client.post(reverse('account_login'), data)

    assert response.status_code == HTTPStatus.OK
    assert not is_logged_in(client)


def test_inactive_user_cannot_log_in(client, make_user, password, is_logged_in):
    make_user(is_active=False)

    login(client, 'ana@example.com', password)

    assert not is_logged_in(client)


def test_login_follows_next(client, make_user, password):
    make_user()

    response = login(client, 'ana@example.com', password, next='/admin/')

    assert response.url == '/admin/'


def test_login_ignores_external_next(client, make_user, password):
    make_user()

    response = login(
        client,
        'ana@example.com',
        password,
        next='https://sitio-malicioso.example.com/',
    )

    assert response.url == reverse('home')


@pytest.mark.parametrize(
    ('extra', 'expires_on_close'),
    [({'remember': 'on'}, False), ({}, True)],
)
def test_remember_me_controls_session(
    client,
    make_user,
    password,
    extra,
    expires_on_close,
):
    make_user()

    login(client, 'ana@example.com', password, **extra)

    assert client.session.get_expire_at_browser_close() is expires_on_close


def test_cannot_log_in_with_username(client, make_user, password, is_logged_in):
    make_user()

    login(client, 'ana', password)

    assert not is_logged_in(client)


def test_admin_backend_accepts_username(client, make_user, password):
    # ModelBackend keeps username login working for the Django admin.
    make_user()

    assert client.login(username='ana', password=password)


def test_logged_in_user_skips_login_page(client, make_user):
    client.force_login(make_user())

    response = client.get(reverse('account_login'))

    assert response.url == reverse('home')


# Google login


def test_google_login_get_asks_for_confirmation(client):
    # A plain GET does not redirect: our button POSTs to skip this page.
    response = client.get(reverse('google_login'))

    assert response.status_code == HTTPStatus.OK


def test_google_request_uses_our_app_and_callback(google_query):
    assert google_query['client_id'] == ['test-client-id']
    assert google_query['redirect_uri'] == [f'http://testserver{GOOGLE_CALLBACK_URL}']


def test_google_requests_authorization_code(google_query):
    assert google_query['response_type'] == ['code']


def test_google_requests_profile_and_email(google_query):
    assert set(google_query['scope'][0].split()) == {'profile', 'email'}


@pytest.mark.usefixtures('google_app')
def test_google_callback_without_code_is_rejected(client, is_logged_in):
    # allauth answers 401 with its error page when Google returns no code.
    response = client.get(GOOGLE_CALLBACK_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert not is_logged_in(client)


@pytest.mark.usefixtures('google_app')
def test_google_callback_access_denied_does_not_log_in(client, is_logged_in):
    client.get(GOOGLE_CALLBACK_URL, {'error': 'access_denied', 'state': 'x'})

    assert not is_logged_in(client)


@pytest.mark.parametrize('field', ['role', 'first_name', 'last_name', 'email'])
def test_google_signup_form_field(field):
    # "Completá tu registro" (first Google login) asks for the role too.
    assert field in SocialSignupForm.base_fields


def test_google_signup_without_pending_login_redirects(client):
    response = client.get(reverse('socialaccount_signup'))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse('account_login'))


# Pages, home and logout


@pytest.mark.parametrize(
    'url_name',
    ['home', 'account_email', 'account_change_password', 'socialaccount_connections'],
)
def test_private_page_redirects_anonymous_to_login(client, url_name):
    response = client.get(reverse(url_name))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse('account_login'))


@pytest.mark.parametrize(
    'url_name',
    ['account_login', 'account_signup', 'account_reset_password'],
)
def test_public_page_is_open(client, url_name):
    assert client.get(reverse(url_name)).status_code == HTTPStatus.OK


def test_home_shows_role(client, make_user):
    client.force_login(make_user(role=User.Role.PHARMACY))

    assert 'Farmacia o laboratorio' in page_content(client, 'home')


@pytest.mark.parametrize(
    ('role', 'message'),
    [
        (User.Role.CUSTOMER, 'tus pedidos'),
        (User.Role.PHARMACY, 'las solicitudes de tu farmacia'),
    ],
)
def test_home_message_depends_on_role(client, make_user, role, message):
    client.force_login(make_user(role=role))

    assert message in page_content(client, 'home')


@pytest.mark.parametrize(
    ('first_name', 'greeting'),
    [('Ana', 'Hola, Ana'), ('', 'Hola, ana@example.com')],
)
def test_home_greeting(client, make_user, first_name, greeting):
    client.force_login(make_user(first_name=first_name))

    assert greeting in page_content(client, 'home')


def test_logout_logs_out_and_redirects_to_login(client, make_user, is_logged_in):
    client.force_login(make_user())

    response = client.post(reverse('account_logout'))

    assert response.url == reverse('account_login')
    assert not is_logged_in(client)


def test_logout_get_only_asks_for_confirmation(client, make_user, is_logged_in):
    client.force_login(make_user())

    response = client.get(reverse('account_logout'))

    assert response.status_code == HTTPStatus.OK
    assert is_logged_in(client)


def test_logout_post_when_anonymous_redirects_to_login(client):
    response = client.post(reverse('account_logout'))

    assert response.url == reverse('account_login')


def test_signup_has_one_show_password_button_per_password(client):
    content = page_content(client, 'account_signup')

    assert content.count('x-on:click="show = !show"') == len(PASSWORD_FIELDS)


def test_pages_render_without_dev_only_tools(client):
    # base.html must not depend on django_browser_reload (dev only).
    assert 'django-browser-reload' not in page_content(client, 'account_login')


# Admin


def test_admin_shows_role_column(admin_client_with_users):
    response = admin_client_with_users.get(reverse('admin:accounts_user_changelist'))

    assert 'column-role' in response.content.decode()


@pytest.mark.parametrize(
    ('role', 'shown', 'hidden'),
    [
        (User.Role.PHARMACY, 'farm@example.com', 'ana@example.com'),
        (User.Role.CUSTOMER, 'ana@example.com', 'farm@example.com'),
    ],
)
def test_admin_filters_by_role(admin_client_with_users, role, shown, hidden):
    response = admin_client_with_users.get(
        reverse('admin:accounts_user_changelist'),
        {'role__exact': role},
    )
    content = response.content.decode()

    assert shown in content
    assert hidden not in content


def test_admin_change_page_has_role_field(admin_client_with_users):
    farm = User.objects.get(username='farm')

    response = admin_client_with_users.get(
        reverse('admin:accounts_user_change', args=[farm.pk]),
    )

    assert 'name="role"' in response.content.decode()


def test_admin_search_by_email(admin_client_with_users):
    response = admin_client_with_users.get(
        reverse('admin:accounts_user_changelist'),
        {'q': 'farm@'},
    )
    content = response.content.decode()

    assert 'farm@example.com' in content
    assert 'ana@example.com' not in content


def test_non_staff_user_cannot_open_admin(client, make_user):
    client.force_login(make_user())

    response = client.get(reverse('admin:accounts_user_changelist'))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse('admin:login'))
