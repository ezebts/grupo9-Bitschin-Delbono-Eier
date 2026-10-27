import json
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.db import transaction

from orders.models import Order
from shared.encryption import (
    AES_GCM_TAG_SIZE,
    EncryptedAttachmentMetadata,
    InvalidEncryptedDataError,
    WrappedKey,
)
from shared.secured_conversations import read_envelope


def prescription_seal_from_json(raw):
    """Validates the prescription metadata posted with the ciphertext."""

    try:
        data = json.loads(raw)
        wrapped_keys = tuple(
            WrappedKey(item['fingerprint'], item['ciphertext'])
            for item in data['wrapped_keys']
        )
        metadata = EncryptedAttachmentMetadata(
            encrypted_filename=data['encrypted_filename'],
            filename_nonce=data['filename_nonce'],
            nonce=data['nonce'],
            content_type=data['content_type'],
            size=0,
        )
    except (TypeError, KeyError, json.JSONDecodeError) as error:
        raise InvalidEncryptedDataError from error
    if not wrapped_keys:
        raise InvalidEncryptedDataError
    return {
        'encrypted_filename': metadata.encrypted_filename,
        'filename_nonce': metadata.filename_nonce,
        'nonce': metadata.nonce,
        'content_type': metadata.content_type,
        'wrapped_keys': [
            {'fingerprint': wrapped.fingerprint, 'ciphertext': wrapped.ciphertext}
            for wrapped in wrapped_keys
        ],
    }


@dataclass(frozen=True)
class SealOrderParams:
    formula: str
    presentation: str
    note: str
    prescription: bytes | None = None
    seal: dict | None = None


@transaction.atomic
def seal_order(user_id, order_id, params: SealOrderParams):
    """Stores the order description and prescription the browser already encrypted."""

    read_envelope(params.formula)
    read_envelope(params.presentation)
    if params.note:
        read_envelope(params.note)
    if params.prescription is not None and params.seal is None:
        raise InvalidEncryptedDataError
    if params.seal is not None and len(params.prescription or b'') < AES_GCM_TAG_SIZE:
        raise InvalidEncryptedDataError

    order = Order.objects.select_for_update(of=('self',)).get(
        pk=order_id,
        client_account__user_id=user_id,
    )
    if order.formula:
        return order

    order.formula = params.formula
    order.presentation = params.presentation
    order.note = params.note
    update_fields = ['formula', 'presentation', 'note']
    if params.prescription is not None:
        order.attach_prescription(
            ContentFile(params.prescription, name='prescription.bin'),
        )
        order.prescription_seal = params.seal
        update_fields.extend(('prescription', 'prescription_seal'))
    order.save(update_fields=update_fields)
    return order
