from dataclasses import replace

import pytest

from accounts.models import DeviceKey, User
from shared.encryption import (
    InvalidEncryptedDataError,
    InvalidPublicKeyError,
    TemporaryWrappedKey,
    WrappedKey,
    fingerprint_public_key,
    generate_temporary_password,
    rewrap_envelope,
)
from shared.tests.encryption import (
    decrypt_message,
    encrypt_message,
    generate_device_key_pair,
)


@pytest.fixture(scope='module')
def device_key_pair():
    return generate_device_key_pair()


def test_message_can_be_encrypted_and_decrypted_with_a_device_key(device_key_pair):
    private_key, public_key, fingerprint = device_key_pair
    envelope = encrypt_message(
        'Mensaje protegido',
        public_keys=((public_key, fingerprint),),
    )

    assert (
        decrypt_message(envelope, private_key=private_key, fingerprint=fingerprint)
        == 'Mensaje protegido'
    )


def test_temporary_key_can_be_rewrapped_for_a_device(device_key_pair):
    private_key, public_key, fingerprint = device_key_pair
    password = generate_temporary_password()
    envelope = encrypt_message(
        'Mensaje protegido',
        temporary_passwords=(('customer', password),),
    )

    rewrapped = rewrap_envelope(envelope, password, public_key, 'customer')

    assert not rewrapped.temporary_wrapped_keys
    assert rewrapped.wrapped_keys[0].fingerprint == fingerprint
    assert (
        decrypt_message(
            rewrapped,
            private_key=private_key,
            fingerprint=fingerprint,
        )
        == 'Mensaje protegido'
    )


@pytest.mark.django_db
def test_device_key_stores_its_public_key_fingerprint(device_key_pair):
    _, public_key, fingerprint = device_key_pair
    user = User.objects.create_user(username='device-key@example.com')

    device_key = DeviceKey.objects.create(user=user, public_key=public_key)

    assert device_key.fingerprint == fingerprint_public_key(public_key) == fingerprint


def test_device_key_rejects_an_invalid_public_key():
    with pytest.raises(InvalidPublicKeyError):
        DeviceKey(user_id=1, public_key='invalid', fingerprint='').save()


@pytest.mark.parametrize(
    ('ciphertext', 'nonce'),
    [
        ('not*base64', 'MDEyMzQ1Njc4OWFi'),
        ('AA', 'MDEyMzQ1Njc4OWFi'),
        ('MDEyMzQ1Njc4OWFi', 'AA'),
    ],
)
def test_envelope_rejects_invalid_ciphertext_or_nonce(
    device_key_pair,
    ciphertext,
    nonce,
):
    _, public_key, fingerprint = device_key_pair
    valid = encrypt_message(
        'Mensaje protegido',
        public_keys=((public_key, fingerprint),),
    )

    with pytest.raises(InvalidEncryptedDataError):
        replace(valid, ciphertext=ciphertext, nonce=nonce)


@pytest.mark.parametrize(
    ('fingerprint', 'wrapped_ciphertext'),
    [
        ('not-a-fingerprint', None),
        ('a' * 64, 'AA'),
    ],
)
def test_wrapped_key_rejects_invalid_fingerprint_or_ciphertext(
    fingerprint,
    wrapped_ciphertext,
):
    if wrapped_ciphertext is None:
        wrapped_ciphertext = 'A' * 512

    with pytest.raises(InvalidEncryptedDataError):
        WrappedKey(fingerprint, wrapped_ciphertext)


def test_wrapped_key_rejects_an_invalid_size(device_key_pair):
    _, _, fingerprint = device_key_pair
    with pytest.raises(InvalidEncryptedDataError):
        WrappedKey(fingerprint, 'A' * 510)


@pytest.mark.parametrize(
    ('ciphertext', 'salt', 'nonce'),
    [
        ('AA', 'A' * 22, 'A' * 16),
        ('A' * 64, 'AA', 'A' * 16),
        ('A' * 64, 'A' * 22, 'AA'),
        ('not*base64', 'A' * 22, 'A' * 16),
    ],
)
def test_temporary_wrapped_key_rejects_invalid_values(ciphertext, salt, nonce):
    with pytest.raises(InvalidEncryptedDataError):
        TemporaryWrappedKey(
            side='customer',
            ciphertext=ciphertext,
            salt=salt,
            nonce=nonce,
        )
