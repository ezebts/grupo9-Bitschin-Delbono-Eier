import json
import re
from http import HTTPStatus
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.commands.register_device import RegisterDeviceParams, register_device
from accounts.models import Pharmacy, PharmacyAccount, User
from orders.models import Order
from orders.tests.test_request_quotes import _customer
from shared.encryption import WrappedKey
from shared.secured_conversations import (
    open_conversation_private_key,
    open_raw,
    open_text,
    read_envelope,
    seal_order_content,
    unwrap_data_key,
)
from shared.tests.encryption import generate_device_public_key

pytestmark = pytest.mark.django_db

FORMULA = 'Hidroquinona 4%'
PRESENTATION = 'Crema 30 g'
FILE = b'%PDF-receta'


def _pharmacy(name, email):
    return Pharmacy.objects.create(
        trade_name=name,
        request_email=email,
        visible=True,
    )


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


def _wraps(order):
    return tuple(
        WrappedKey(item['fingerprint'], item['ciphertext'])
        for item in order.prescription_seal['wrapped_keys']
    )


def _fingerprints(value):
    return {item.fingerprint for item in read_envelope(value).wrapped_keys}


def _submit_sealed_order(client):
    sofia = _customer()
    client.force_login(sofia)
    first = _pharmacy('Farmacia Norte', 'norte@example.com')
    second = _pharmacy('Farmacia Sur', 'sur@example.com')
    session = client.session
    session['new_order'] = {
        'preparation_tag': 'creams',
        'urgency': 'no_rush',
        'delivery_preferences': ['pickup'],
        'search_area': 'Palermo',
        'latitude': -34.58,
        'longitude': -58.41,
        'address': '',
        'locality': '',
        'postal_code': '',
        'formula': FORMULA,
        'presentation': PRESENTATION,
    }
    session.save()
    prepared = client.post(
        reverse('orders:choose'),
        {'pharmacy': [first.id, second.id]},
        headers={'X-Order-Prepare': '1'},
    )
    payload = prepared.json()
    order = Order.objects.get(pk=payload['order_id'])
    conversations = {
        item.pharmacy_id: item.conversation
        for item in order.quote_requests.select_related('conversation')
    }
    created_formula = order.formula
    sealed, ciphertext, seal = seal_order_content(
        {'formula': FORMULA, 'presentation': PRESENTATION, 'note': 'Sin alcohol'},
        [
            conversations[first.id].server_public_key,
            conversations[second.id].server_public_key,
        ],
        filename='receta.pdf',
        file=FILE,
        content_type='application/pdf',
    )
    saved = client.post(
        payload['seal_url'],
        {
            'formula': sealed['formula'],
            'presentation': sealed['presentation'],
            'note': sealed['note'],
            'prescription_seal': json.dumps(seal),
            'prescription_file': SimpleUploadedFile('prescription.bin', ciphertext),
        },
    )
    order.refresh_from_db()
    stored = order.prescription.read()
    order.prescription.close()
    return {
        'prepared': prepared,
        'saved': saved,
        'order': order,
        'stored': stored,
        'first': first,
        'second': second,
        'conversations': conversations,
        'returned': {item['fingerprint'] for item in payload['public_keys']},
        'created_formula': created_formula,
    }


def test_the_order_is_stored_as_one_sealed_prescription(client):
    submitted = _submit_sealed_order(client)
    order = submitted['order']
    first = submitted['conversations'][submitted['first'].id]
    second = submitted['conversations'][submitted['second'].id]
    first_key = open_conversation_private_key(first.server_private_key)

    assert submitted['created_formula'] == ''
    assert FORMULA not in order.formula
    assert FORMULA not in submitted['prepared'].content.decode()
    assert first.server_key_fingerprint in submitted['returned']
    assert second.server_key_fingerprint in submitted['returned']
    assert submitted['saved'].status_code == HTTPStatus.OK
    assert PRESENTATION not in order.presentation
    assert 'Sin alcohol' not in order.note
    assert re.fullmatch(r'[0-9a-f]{32}', Path(order.prescription.name).name)
    assert submitted['stored'] != FILE
    assert open_text(read_envelope(order.formula), first_key) == FORMULA
    assert unwrap_data_key(
        read_envelope(order.formula),
        first_key,
    ) == unwrap_data_key(read_envelope(order.presentation), first_key)
    assert (
        open_raw(
            submitted['stored'],
            order.prescription_seal['nonce'],
            first_key,
            _wraps(order),
        )
        == FILE
    )


def test_the_server_wrap_leaves_when_the_last_pharmacy_registers(client):
    submitted = _submit_sealed_order(client)
    order = submitted['order']
    first = submitted['conversations'][submitted['first'].id]
    second = submitted['conversations'][submitted['second'].id]
    second_key = open_conversation_private_key(second.server_private_key)
    first_fingerprint = first.server_key_fingerprint
    second_fingerprint = second.server_key_fingerprint
    pharmacist = _pharmacist('norte-cuenta@example.com', submitted['first'])
    public_key, device_fingerprint = generate_device_public_key()
    register_device(pharmacist.id, RegisterDeviceParams(public_key=public_key))

    order.refresh_from_db()
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.server_private_key == ''
    assert second.server_private_key
    assert first_fingerprint not in _fingerprints(order.formula)
    assert device_fingerprint in _fingerprints(order.formula)
    assert second_fingerprint in {item.fingerprint for item in _wraps(order)}
    assert open_text(read_envelope(order.formula), second_key) == FORMULA

    other = _pharmacist('sur-cuenta@example.com', submitted['second'])
    other_key, other_fingerprint = generate_device_public_key()
    register_device(other.id, RegisterDeviceParams(public_key=other_key))
    order.refresh_from_db()
    second.refresh_from_db()
    assert second.server_private_key == ''
    remaining = _fingerprints(order.formula) | {
        item.fingerprint for item in _wraps(order)
    }
    assert first_fingerprint not in remaining
    assert second_fingerprint not in remaining
    assert device_fingerprint in remaining
    assert other_fingerprint in remaining
