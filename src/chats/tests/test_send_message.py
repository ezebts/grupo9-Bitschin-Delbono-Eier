import pytest

from accounts.models import User
from chats.commands.send_message import send_message
from chats.commands.send_system_message import send_system_message
from chats.models import Conversation, MessageAuthor, UserMessage
from chats.queries.customer_inbox import get_customer_conversation
from chats.queries.pharmacy_inbox import get_pharmacy_inbox
from chats.tests.support import open_conversation

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


@pytest.fixture
def customer():
    return _user(
        'sofia@example.com',
        User.Role.CUSTOMER,
        first_name='Sofía',
        last_name='Martínez',
    )


@pytest.fixture
def pharmacy():
    return _user('staff@example.com', User.Role.PHARMACY)


@pytest.fixture
def conversation(customer, pharmacy):
    _, conversation = open_conversation(customer, pharmacy)
    return conversation


def test_post_records_the_author_and_the_text(customer, conversation):
    send_message(customer.id, conversation.id, '¿Ya está lista mi crema?')

    message = UserMessage.objects.get(conversation=conversation)
    assert message.body == '¿Ya está lista mi crema?'
    assert message.message_author == MessageAuthor(
        customer.id,
        customer.get_full_name() or customer.email,
    )
    assert message.is_customer
    assert list(conversation.messages.values_list('body', flat=True)) == [
        'La solicitud también llega por mail',
        '¿Ya está lista mi crema?',
    ]


def test_pharmacy_cannot_post_in_another_conversation(customer, pharmacy):
    other = _user('otra-farmacia@example.com', User.Role.PHARMACY)
    _, other_conversation = open_conversation(customer, other, formula='Otra')

    with pytest.raises(Conversation.DoesNotExist):
        send_message(pharmacy.id, other_conversation.id, 'Mensaje no autorizado')

    assert list(other_conversation.messages.values_list('body', flat=True)) == [
        'La solicitud también llega por mail',
    ]


def test_customer_cannot_post_in_another_conversation(customer, pharmacy):
    other = _user(
        'otra@example.com',
        User.Role.CUSTOMER,
        first_name='Otra',
        last_name='Cliente',
    )
    _, other_conversation = open_conversation(other, pharmacy, formula='Privada')

    with pytest.raises(Conversation.DoesNotExist):
        send_message(customer.id, other_conversation.id, 'Mensaje no autorizado')

    assert list(other_conversation.messages.values_list('body', flat=True)) == [
        'La solicitud también llega por mail',
    ]


def test_customer_message_waits_for_the_pharmacy(customer, pharmacy):
    order, conversation = open_conversation(customer, pharmacy)
    send_message(customer.id, conversation.id, '¿Ya está lista mi crema?')
    send_message(pharmacy.id, conversation.id, 'Sí, ya está lista para retirar.')
    send_message(customer.id, conversation.id, 'Gracias, paso por la tarde.')

    opened = get_customer_conversation(customer.id, order.id, conversation.id)
    inbox = get_pharmacy_inbox(pharmacy.id)

    assert opened.messages[-1].body == 'Gracias, paso por la tarde.'
    assert opened.messages[-1].is_customer
    assert inbox.conversations[0].waiting_for_pharmacy


def test_pharmacy_reply_is_no_longer_waiting(customer, pharmacy, conversation):
    send_message(customer.id, conversation.id, '¿Ya está lista mi crema?')
    send_message(pharmacy.id, conversation.id, 'Sí, ya está lista para retirar.')

    inbox = get_pharmacy_inbox(pharmacy.id)
    listed = inbox.conversations[0]

    assert listed.last_message.body == 'Sí, ya está lista para retirar.'
    assert not listed.waiting_for_pharmacy
    assert listed.last_message.is_pharmacy


def test_system_message_is_not_a_user_message(customer, pharmacy):
    order, conversation = open_conversation(customer, pharmacy)
    send_message(customer.id, conversation.id, '¿Ya está lista mi crema?')
    send_message(pharmacy.id, conversation.id, 'Sí, ya está lista para retirar.')
    send_system_message(
        conversation.id,
        'Enviamos tu solicitud por mail a la farmacia',
    )

    opened = get_customer_conversation(customer.id, order.id, conversation.id)
    inbox = get_pharmacy_inbox(pharmacy.id)

    assert opened.messages[-1].is_system
    assert opened.messages[-1].body == 'Enviamos tu solicitud por mail a la farmacia'
    assert opened.messages[1].is_customer
    assert not inbox.conversations[0].waiting_for_pharmacy
