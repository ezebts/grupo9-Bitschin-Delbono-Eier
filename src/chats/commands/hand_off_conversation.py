from django.db import transaction

from chats.models import Conversation, Message
from shared.encryption import (
    EncryptedEnvelope,
    InvalidEncryptedDataError,
    WrappedKey,
)
from shared.secured_conversations import (
    envelope_text,
    open_conversation_private_key,
    read_envelope,
    replace_server_wrap,
)


def _rewrapped_prescription(order, private_key, fingerprint, public_key):
    seal = order.prescription_seal
    if not seal:
        return False
    try:
        sealed_file = EncryptedEnvelope(
            ciphertext=seal['encrypted_filename'],
            nonce=seal['filename_nonce'],
            wrapped_keys=tuple(
                WrappedKey(item['fingerprint'], item['ciphertext'])
                for item in seal['wrapped_keys']
            ),
        )
    except (KeyError, TypeError, InvalidEncryptedDataError):
        return False
    updated = replace_server_wrap(sealed_file, private_key, fingerprint, public_key)
    if updated == sealed_file:
        return False
    order.prescription_seal = {
        **seal,
        'wrapped_keys': [
            {'fingerprint': item.fingerprint, 'ciphertext': item.ciphertext}
            for item in updated.wrapped_keys
        ],
    }
    return True


def _rewrapped(value, private_key, fingerprint, public_key):
    try:
        envelope = read_envelope(value)
    except InvalidEncryptedDataError:
        return None
    updated = replace_server_wrap(envelope, private_key, fingerprint, public_key)
    if updated == envelope:
        return None
    return envelope_text(updated)


@transaction.atomic
def hand_off_pharmacy_conversations(pharmacy_id, public_key):
    """Replaces this pharmacy's server wrap with its first device key."""

    conversations = Conversation.objects.filter(
        quote_request__pharmacy_id=pharmacy_id,
    ).exclude(server_private_key='')

    for conversation in conversations.select_related('quote_request__order'):
        private_key = open_conversation_private_key(conversation.server_private_key)
        fingerprint = conversation.server_key_fingerprint
        messages = conversation.messages.exclude(sender=Message.Sender.SYSTEM)
        for message in messages:
            body = _rewrapped(message.body, private_key, fingerprint, public_key)
            if body is None:
                continue
            message.body = body
            message.save(update_fields=['body'])

        order = conversation.quote_request.order
        changed = []
        for field in ('formula', 'presentation', 'note'):
            sealed = _rewrapped(
                getattr(order, field),
                private_key,
                fingerprint,
                public_key,
            )
            if sealed is None:
                continue
            setattr(order, field, sealed)
            changed.append(field)
        if _rewrapped_prescription(order, private_key, fingerprint, public_key):
            changed.append('prescription_seal')
        if changed:
            order.save(update_fields=changed)

        conversation.server_public_key = ''
        conversation.server_key_fingerprint = ''
        conversation.server_private_key = ''
        conversation.save(
            update_fields=[
                'server_public_key',
                'server_key_fingerprint',
                'server_private_key',
            ],
        )
