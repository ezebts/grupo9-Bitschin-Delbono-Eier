from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from accounts.models import MailPreferences, PharmacyMailPreferences, User
from chats.commands.send_message import send_message
from chats.commands.send_notice_mail import send_order_status_notice
from chats.tests.support import open_conversation
from orders.commands.accept_quote import accept_quote
from orders.commands.advance_order import AdvanceOrderParams, advance_order
from orders.commands.submit_quote import submit_quote
from orders.models import QuoteRequestStatus
from orders.tests.test_quote_management import _params

pytestmark = pytest.mark.django_db


def _user(username, role, first_name='', last_name=''):
    user = User(
        username=username,
        email=username,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    user.set_unusable_password()
    user.save()
    return user


def _conversation():
    customer = _user(
        'sofia@example.com',
        User.Role.CUSTOMER,
        first_name='Sofía',
        last_name='Martínez',
    )
    pharmacy_user = _user('staff@example.com', User.Role.PHARMACY)
    _order, conversation = open_conversation(customer, pharmacy_user)
    pharmacy = conversation.quote_request.pharmacy
    pharmacy.request_email = 'farmacia@example.com'
    pharmacy.trade_name = 'Abrate'
    pharmacy.save(update_fields=['request_email', 'trade_name'])
    mail.outbox.clear()
    return customer, pharmacy_user, conversation


def test_pharmacy_replies_email_the_client_at_most_every_15_minutes(
    django_capture_on_commit_callbacks,
):
    customer, pharmacy_user, conversation = _conversation()

    with django_capture_on_commit_callbacks(execute=True):
        send_message(pharmacy_user.id, conversation.id, 'Ya lo estoy viendo')
        send_message(pharmacy_user.id, conversation.id, 'Te paso el precio')

    assert [item.subject for item in mail.outbox] == ['La farmacia te escribió']
    assert mail.outbox[0].to == [customer.email]
    assert 'Abrate respondió' in mail.outbox[0].body

    conversation.client_notified_at = timezone.now() - timedelta(minutes=16)
    conversation.save(update_fields=['client_notified_at'])

    with django_capture_on_commit_callbacks(execute=True):
        send_message(pharmacy_user.id, conversation.id, 'Sigue en pie')

    assert [item.subject for item in mail.outbox] == [
        'La farmacia te escribió',
        'La farmacia te escribió',
    ]


def test_a_quote_email_uses_the_same_15_minute_window(
    django_capture_on_commit_callbacks,
):
    _customer, pharmacy_user, conversation = _conversation()

    with django_capture_on_commit_callbacks(execute=True):
        submit_quote(pharmacy_user.id, conversation.id, _params())
        send_message(pharmacy_user.id, conversation.id, 'Quedó cargado')

    assert [item.subject for item in mail.outbox] == ['Recibiste un presupuesto']
    assert 'envió un presupuesto' in mail.outbox[0].body


def test_client_can_turn_off_reply_mail(django_capture_on_commit_callbacks):
    customer, pharmacy_user, conversation = _conversation()
    account = customer.client_account
    account.update_mail_preferences(
        MailPreferences(on_reply=False, on_status_change=True),
    )
    account.save(update_fields=['_mail_preferences'])

    with django_capture_on_commit_callbacks(execute=True):
        send_message(pharmacy_user.id, conversation.id, 'Hola')

    assert mail.outbox == []


def test_client_messages_email_the_pharmacy_at_most_every_15_minutes(
    django_capture_on_commit_callbacks,
):
    customer, _pharmacy_user, conversation = _conversation()

    with django_capture_on_commit_callbacks(execute=True):
        send_message(customer.id, conversation.id, '¿Llega hoy?')
        send_message(customer.id, conversation.id, 'Gracias')

    assert [item.subject for item in mail.outbox] == ['El cliente te escribió']
    assert mail.outbox[0].to == ['farmacia@example.com']
    assert 'Sofía Martínez' in mail.outbox[0].body


def test_accepting_a_quote_mails_only_the_pharmacy(
    django_capture_on_commit_callbacks,
):
    customer, _pharmacy_user, conversation = _conversation()
    quote_request = conversation.quote_request
    quote_request.status = QuoteRequestStatus.ACCEPTED

    with django_capture_on_commit_callbacks(execute=True):
        quote_request.save(update_fields=['status'])

    subjects = sorted(item.subject for item in mail.outbox)
    assert subjects == sorted(
        [
            'Aceptaron tu presupuesto',
            'El cliente aceptó tu presupuesto',
        ],
    )
    assert all(item.to != [customer.email] for item in mail.outbox)


def test_rejecting_a_quote_mails_only_the_pharmacy(
    django_capture_on_commit_callbacks,
):
    _customer, _pharmacy_user, conversation = _conversation()
    quote_request = conversation.quote_request
    quote_request.status = QuoteRequestStatus.REJECTED

    with django_capture_on_commit_callbacks(execute=True):
        quote_request.save(update_fields=['status'])

    assert sorted(item.subject for item in mail.outbox) == sorted(
        [
            'Rechazaron tu presupuesto',
            'El cliente rechazó tu presupuesto',
        ],
    )


def test_pharmacy_can_turn_off_each_notice(django_capture_on_commit_callbacks):
    customer, _pharmacy_user, conversation = _conversation()
    pharmacy = conversation.quote_request.pharmacy
    pharmacy.update_mail_preferences(
        PharmacyMailPreferences(on_reply=False, on_quote_status=True),
    )
    pharmacy.save(update_fields=['_mail_preferences'])

    with django_capture_on_commit_callbacks(execute=True):
        send_message(customer.id, conversation.id, 'Hola')

    assert mail.outbox == []

    quote_request = conversation.quote_request
    quote_request.status = QuoteRequestStatus.REJECTED
    with django_capture_on_commit_callbacks(execute=True):
        quote_request.save(update_fields=['status'])

    assert [item.subject for item in mail.outbox] == ['Rechazaron tu presupuesto']


@pytest.mark.parametrize(
    'status_label',
    ['en preparación', 'listo para retirar', 'entregado'],
)
def test_order_status_mail_uses_the_new_status(status_label):
    customer, _pharmacy_user, conversation = _conversation()

    send_order_status_notice(conversation.id, status_label)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [customer.email]
    assert mail.outbox[0].subject == f'Tu pedido está {status_label}'
    assert f'ahora está {status_label}' in mail.outbox[0].body


def test_order_status_mail_respects_the_client_preference():
    customer, _pharmacy_user, conversation = _conversation()
    account = customer.client_account
    account.update_mail_preferences(
        MailPreferences(on_reply=True, on_status_change=False),
    )
    account.save(update_fields=['_mail_preferences'])

    send_order_status_notice(conversation.id, 'entregado')

    assert mail.outbox == []


def test_moving_an_order_mails_the_client(django_capture_on_commit_callbacks):
    customer, pharmacy_user, conversation = _conversation()
    submit_quote(pharmacy_user.id, conversation.id, _params())
    accept_quote(customer.id, conversation.id)
    estimated_at = timezone.localdate() + timedelta(days=2)

    with django_capture_on_commit_callbacks(execute=True):
        advance_order(
            pharmacy_user.id,
            conversation.id,
            AdvanceOrderParams(estimated_at=estimated_at),
        )

    assert [item.subject for item in mail.outbox] == ['Tu pedido está en preparación']
    assert mail.outbox[0].to == [customer.email]
