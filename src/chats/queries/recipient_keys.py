from accounts.models import PharmacyAccount
from accounts.queries.device_keys import get_pharmacy_device_keys, get_user_device_keys
from chats.models import Conversation
from orders.models import Order


def recipient_public_keys(conversation_id):
    """Public keys the browser wraps a new message to."""

    conversation = Conversation.objects.select_related(
        'quote_request__order__client_account',
        'quote_request__pharmacy',
    ).get(pk=conversation_id)
    customer_id = conversation.quote_request.order.client_account.user_id
    keys = [
        {'public_key': item.public_key, 'fingerprint': item.fingerprint}
        for item in get_user_device_keys(customer_id)
    ]
    pharmacy_id = conversation.quote_request.pharmacy_id
    if PharmacyAccount.objects.filter(pharmacy_id=pharmacy_id).exists():
        keys.extend(
            {'public_key': item.public_key, 'fingerprint': item.fingerprint}
            for item in get_pharmacy_device_keys(pharmacy_id)
        )
    elif conversation.server_public_key:
        keys.append(
            {
                'public_key': conversation.server_public_key,
                'fingerprint': conversation.server_key_fingerprint,
            }
        )
    return keys


def order_recipient_public_keys(order_id):
    """Public keys that can open the order description and the prescription."""

    order = Order.objects.select_related('client_account').get(pk=order_id)
    pairs = [
        (item.fingerprint, item.public_key)
        for item in get_user_device_keys(order.client_account.user_id)
    ]

    conversations = Conversation.objects.filter(
        quote_request__order_id=order_id,
    )
    pharmacy_ids = conversations.values_list('quote_request__pharmacy_id', flat=True)
    with_account = set(
        PharmacyAccount.objects.filter(pharmacy_id__in=pharmacy_ids).values_list(
            'pharmacy_id',
            flat=True,
        ),
    )
    for conversation in conversations.select_related('quote_request'):
        pharmacy_id = conversation.quote_request.pharmacy_id
        if pharmacy_id in with_account:
            pairs.extend(
                (item.fingerprint, item.public_key)
                for item in get_pharmacy_device_keys(pharmacy_id)
            )
        else:
            pairs.append(
                (conversation.server_key_fingerprint, conversation.server_public_key),
            )

    keys = {fingerprint: public_key for fingerprint, public_key in pairs if fingerprint}
    return [
        {'public_key': public_key, 'fingerprint': fingerprint}
        for fingerprint, public_key in keys.items()
    ]
