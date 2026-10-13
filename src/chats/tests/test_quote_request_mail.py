import re

import pytest
from django.core import mail

from accounts.models import InvitationLink, Pharmacy, PharmacyAccount, User
from chats.models import Message
from orders.commands.create_order import CreateOrderParams, create_order
from orders.commands.request_quote import request_quote
from orders.tests.test_request_quotes import _customer

pytestmark = pytest.mark.django_db


long_formula = f'Hidroquinona 4% {"componente " * 20}'


def _order(customer):
    return create_order(
        customer.id,
        CreateOrderParams(
            preparation_tag='creams',
            presentation='Crema 30 g',
            formula=long_formula,
            urgency='this_week',
            delivery_preferences=('pickup',),
            note='',
        ),
    )


def test_new_quote_request_emails_the_pharmacy(django_capture_on_commit_callbacks):
    sofia = _customer()
    pharmacy = Pharmacy.objects.create(
        trade_name='Farmacia Galénica Palermo',
        request_email='farmacia.galenica@gmail.com',
    )

    with django_capture_on_commit_callbacks(execute=True):
        request_quote(_order(sofia).id, pharmacy.id)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ['farmacia.galenica@gmail.com']
    assert message.subject == 'Nueva solicitud de presupuesto'
    assert 'Farmacia Galénica Palermo' in message.body
    assert 'Sofía Martínez' in message.body
    assert 'Hidroquinona 4%' in message.body
    assert long_formula not in message.body
    assert '...' in message.body
    assert 'Crema 30 g' in message.body
    assert 'Esta semana' in message.body
    assert 'Retiro en farmacia' in message.body
    assert message.content_subtype == 'html'
    found = re.search(r'href="([^"]+)"', message.body)
    invitation = InvitationLink.from_value(found.group(1))
    assert invitation.email == pharmacy.request_email
    assert invitation.next_url.startswith('/chats/?conversation_id=')
    assert Message.objects.filter(
        body='La solicitud también llega por mail',
    ).exists()


def test_pharmacy_with_an_account_gets_the_conversation_link(
    django_capture_on_commit_callbacks,
):
    sofia = _customer()
    staff = User(
        username='staff@galenica.test',
        email='staff@galenica.test',
        role=User.Role.PHARMACY,
        first_name='Ana',
        last_name='Pérez',
    )
    staff.set_unusable_password()
    staff.save()
    pharmacy = Pharmacy.objects.create(
        trade_name='Farmacia Galénica Palermo',
        request_email='farmacia.galenica@gmail.com',
    )
    PharmacyAccount.objects.create(user=staff, pharmacy=pharmacy)

    with django_capture_on_commit_callbacks(execute=True):
        request_quote(_order(sofia).id, pharmacy.id)

    found = re.search(r'href="([^"]+)"', mail.outbox[0].body)
    assert '/accounts/invitation/' not in found.group(1)
    assert '/chats/?conversation_id=' in found.group(1)


def test_quote_request_without_an_email_does_not_send(
    django_capture_on_commit_callbacks,
):
    sofia = _customer()
    pharmacy = Pharmacy.objects.create(trade_name='Sin mail')

    with django_capture_on_commit_callbacks(execute=True):
        request_quote(_order(sofia).id, pharmacy.id)

    assert getattr(mail, 'outbox', []) == []
    assert Message.objects.filter(
        body='La solicitud también llega por mail',
    ).exists()
