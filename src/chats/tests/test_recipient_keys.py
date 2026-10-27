import pytest

from accounts.commands.register_device import RegisterDeviceParams, register_device
from accounts.models import Pharmacy, PharmacyAccount, User
from chats.models import Conversation
from chats.queries.recipient_keys import recipient_public_keys
from orders.commands.create_order import CreateOrderParams, create_order
from orders.commands.request_quote import request_quote
from orders.tests.test_request_quotes import _customer
from shared.tests.encryption import generate_device_public_key

pytestmark = pytest.mark.django_db


def _pharmacist(email, pharmacy):
    user = User(
        username=email,
        email=email,
        role=User.Role.PHARMACY,
        first_name='Galénica',
        last_name='Palermo',
    )
    user.set_unusable_password()
    user.save()
    PharmacyAccount.objects.create(user=user, pharmacy=pharmacy)
    return user


def _order(customer, pharmacy):
    order = create_order(
        customer.id,
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
    return Conversation.objects.get(pk=quote_request.conversation.id)


def test_a_pharmacy_device_can_open_a_new_message():
    sofia = _customer()
    pharmacy = Pharmacy.objects.create(
        trade_name='Farmacia con cuenta',
        request_email='con-cuenta@example.com',
    )
    pharmacist = _pharmacist('farm@example.com', pharmacy)
    public_key, fingerprint = generate_device_public_key()
    register_device(pharmacist.id, RegisterDeviceParams(public_key=public_key))

    conversation = _order(sofia, pharmacy)

    assert conversation.server_private_key == ''
    fingerprints = {
        item['fingerprint'] for item in recipient_public_keys(conversation.id)
    }
    assert fingerprints == {fingerprint}


def test_a_pharmacy_account_without_a_device_cannot_open_a_message():
    sofia = _customer()
    pharmacy = Pharmacy.objects.create(
        trade_name='Farmacia sin dispositivo',
        request_email='sin-dispositivo@example.com',
    )
    _pharmacist('sin-dispositivo@example.com', pharmacy)

    conversation = _order(sofia, pharmacy)

    assert conversation.server_private_key == ''
    assert recipient_public_keys(conversation.id) == []
