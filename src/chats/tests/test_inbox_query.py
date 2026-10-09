import pytest

from accounts.models import User
from chats.commands.send_message import send_message
from chats.models import Conversation
from chats.queries.customer_inbox import get_customer_inbox
from chats.queries.pharmacy_inbox import get_pharmacy_inbox

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
    other = _user('otra@example.com', User.Role.CUSTOMER, first_name='Otra')
    own = Conversation.objects.create(customer=sofia)
    send_message(sofia.id, own.id, '¿Ya está lista mi crema?')
    private = Conversation.objects.create(customer=other)
    send_message(other.id, private.id, 'Consulta privada')

    inbox = get_customer_inbox(sofia.id)

    assert [item.id for item in inbox.conversations] == [own.id]
    assert inbox.conversations[0].last_message.body == '¿Ya está lista mi crema?'


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
    Conversation.objects.create(
        customer=sofia,
        pharmacy=pharmacy,
        title='Crema',
    )
    Conversation.objects.create(
        customer=tomas,
        pharmacy=pharmacy,
        title='Jarabe',
    )
    Conversation.objects.create(
        customer=sofia,
        pharmacy=other_pharmacy,
        title='Crema',
    )

    inbox = get_pharmacy_inbox(pharmacy.id, 'Sofía')

    assert [item.title for item in inbox.conversations] == ['Crema']
