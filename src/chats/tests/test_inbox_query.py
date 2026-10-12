import pytest

from accounts.models import User
from chats.commands.send_message import send_message
from chats.queries.customer_inbox import (
    get_customer_conversation,
    get_customer_inbox,
)
from chats.queries.pharmacy_inbox import get_conversation, get_pharmacy_inbox
from chats.tests.support import open_conversation
from orders.models import Order

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


def test_customer_inbox_lists_only_their_conversations():
    sofia = _user(
        'sofia@example.com',
        User.Role.CUSTOMER,
        first_name='Sofía',
        last_name='Martínez',
    )
    other = _user(
        'otra@example.com',
        User.Role.CUSTOMER,
        first_name='Otra',
        last_name='Paz',
    )
    pharmacy = _user('staff@example.com', User.Role.PHARMACY)
    order, own = open_conversation(sofia, pharmacy, formula='Crema')
    send_message(sofia.id, own.id, '¿Ya está lista mi crema?')
    private_order, private = open_conversation(
        other,
        pharmacy,
        formula='Consulta privada',
    )
    send_message(other.id, private.id, 'Consulta privada')

    inbox = get_customer_inbox(sofia.id, order.id)
    opened = get_customer_conversation(sofia.id, order.id, own.id)

    assert [item.id for item in inbox.conversations] == [own.id]
    assert inbox.code == order.code
    assert inbox.progress_label == 'Esperando presupuestos'
    assert inbox.preparation_label == 'Cremas y geles'
    assert inbox.presentation == '30 g'
    assert inbox.urgency_label == 'Sin apuro'
    assert inbox.delivery_label == 'Retiro en farmacia'
    assert inbox.conversations[0].pharmacy_name == 'Abrate'
    assert inbox.conversations[0].last_message.body == '¿Ya está lista mi crema?'
    assert opened.pharmacy_name == 'Abrate'
    with pytest.raises(Order.DoesNotExist):
        get_customer_inbox(sofia.id, private_order.id)


def test_customer_inbox_filters_by_order():
    sofia = _user(
        'sofia@example.com',
        User.Role.CUSTOMER,
        first_name='Sofía',
        last_name='Martínez',
    )
    pharmacy = _user('staff@example.com', User.Role.PHARMACY)
    first_order, first = open_conversation(sofia, pharmacy, formula='Crema')
    second_order, second = open_conversation(sofia, pharmacy, formula='Jarabe')

    inbox = get_customer_inbox(sofia.id, first_order.id)
    other = get_customer_inbox(sofia.id, second_order.id)

    assert [item.id for item in inbox.conversations] == [first.id]
    assert [item.id for item in other.conversations] == [second.id]


def test_pharmacy_inbox_search_filters_by_customer_name():
    sofia = _user(
        'sofia@example.com',
        User.Role.CUSTOMER,
        first_name='Sofía',
        last_name='Martínez',
    )
    tomas = _user(
        'tomas@example.com',
        User.Role.CUSTOMER,
        first_name='Tomás',
        last_name='Rodríguez',
    )
    pharmacy = _user('staff@example.com', User.Role.PHARMACY)
    other_pharmacy = _user('otra-farmacia@example.com', User.Role.PHARMACY)
    _, sofia_chat = open_conversation(sofia, pharmacy, formula='Crema')
    open_conversation(tomas, pharmacy, formula='Jarabe')
    open_conversation(sofia, other_pharmacy, formula='Crema')

    inbox = get_pharmacy_inbox(pharmacy.id, 'Sofía')
    opened = get_conversation(pharmacy.id, sofia_chat.id)

    assert [item.title for item in inbox.conversations] == ['Crema']
    assert opened.customer_name == 'Sofía Martínez'
