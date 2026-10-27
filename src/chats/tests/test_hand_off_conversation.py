import pytest

from accounts.commands.register_device import RegisterDeviceParams, register_device
from accounts.models import Pharmacy, PharmacyAccount, User
from chats.commands.send_message import send_message
from chats.models import Conversation
from orders.commands.create_order import CreateOrderParams, create_order
from orders.commands.request_quote import request_quote
from orders.tests.test_request_quotes import _customer
from shared.secured_conversations import envelope_text, read_envelope, seal_text
from shared.tests.encryption import generate_device_public_key

pytestmark = pytest.mark.django_db


def test_first_pharmacy_device_replaces_the_server_wrap():
    sofia = _customer()
    pharmacy = Pharmacy.objects.create(
        trade_name='Farmacia sin cuenta',
        request_email='sin-cuenta@example.com',
    )
    order = create_order(
        sofia.id,
        CreateOrderParams(
            preparation_tag='creams',
            presentation='Crema 30 g',
            formula='Hidroquinona 4%',
            urgency='no_rush',
            delivery_preferences=('pickup',),
            note='',
        ),
    )
    quote_request = request_quote(order.id, pharmacy.id)
    conversation = Conversation.objects.get(pk=quote_request.conversation.id)
    server_fingerprint = conversation.server_key_fingerprint
    assert conversation.server_private_key

    plaintext = 'La fórmula es hidroquinona'
    envelope = seal_text(plaintext, [conversation.server_public_key])
    send_message(sofia.id, conversation.id, envelope_text(envelope))
    order.formula = envelope_text(
        seal_text('Hidroquinona 4%', [conversation.server_public_key]),
    )
    order.save(update_fields=['formula'])

    pharmacist = User(
        username='farm@example.com',
        email='farm@example.com',
        role=User.Role.PHARMACY,
        first_name='Galénica',
        last_name='Palermo',
    )
    pharmacist.set_unusable_password()
    pharmacist.save()
    PharmacyAccount.objects.create(user=pharmacist, pharmacy=pharmacy)
    public_key, fingerprint = generate_device_public_key()
    register_device(pharmacist.id, RegisterDeviceParams(public_key=public_key))

    conversation.refresh_from_db()
    assert conversation.server_private_key == ''
    assert conversation.server_public_key == ''
    message = conversation.messages.exclude(sender='system').get()
    assert plaintext not in message.body
    opened = read_envelope(message.body)
    assert server_fingerprint not in {item.fingerprint for item in opened.wrapped_keys}
    assert fingerprint in {item.fingerprint for item in opened.wrapped_keys}

    order.refresh_from_db()
    assert 'Hidroquinona 4%' not in order.formula
    formula = read_envelope(order.formula)
    assert fingerprint in {item.fingerprint for item in formula.wrapped_keys}
    assert server_fingerprint not in {item.fingerprint for item in formula.wrapped_keys}
