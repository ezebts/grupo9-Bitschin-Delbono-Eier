from dataclasses import replace

import pytest

from accounts.models import DeviceKey, User
from shared.encryption import (
    EncryptedEnvelope,
    InvalidEncryptedDataError,
    InvalidPublicKeyError,
    TemporaryWrappedKey,
    WrappedKey,
    fingerprint_public_key,
)
from shared.tests.encryption import generate_device_public_key


@pytest.fixture(scope='module')
def device_public_key():
    return generate_device_public_key()


def test_encrypted_envelope_accepts_a_device_wrapped_key(device_public_key):
    _, fingerprint = device_public_key
    wrapped_key = WrappedKey(fingerprint, 'A' * 512)

    envelope = EncryptedEnvelope(
        ciphertext='A' * 22,
        nonce='MDEyMzQ1Njc4OWFi',
        wrapped_keys=(wrapped_key,),
    )

    assert envelope.wrapped_keys == (wrapped_key,)


def test_encrypted_envelope_accepts_a_temporary_wrapped_key():
    wrapped_key = TemporaryWrappedKey(
        side='customer',
        ciphertext='A' * 64,
        salt='A' * 22,
        nonce='A' * 16,
    )

    envelope = EncryptedEnvelope(
        ciphertext='A' * 22,
        nonce='MDEyMzQ1Njc4OWFi',
        wrapped_keys=(),
        temporary_wrapped_keys=(wrapped_key,),
    )

    assert envelope.temporary_wrapped_keys == (wrapped_key,)


@pytest.mark.django_db
def test_device_key_stores_its_public_key_fingerprint(device_public_key):
    public_key, fingerprint = device_public_key
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
    device_public_key,
    ciphertext,
    nonce,
):
    _, fingerprint = device_public_key
    valid = EncryptedEnvelope(
        ciphertext='A' * 22,
        nonce='MDEyMzQ1Njc4OWFi',
        wrapped_keys=(WrappedKey(fingerprint, 'A' * 512),),
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


def test_wrapped_key_rejects_an_invalid_size(device_public_key):
    _, fingerprint = device_public_key
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
