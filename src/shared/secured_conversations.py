import base64
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from shared.encryption import (
    RSA_KEY_SIZE,
    EncryptedEnvelope,
    InvalidEncryptedDataError,
    WrappedKey,
    fingerprint_public_key,
    validate_rsa_public_key,
)
from shared.encryption import (
    _decode_base64 as decode_base64,
)

AES_KEY_SIZE = 32
_OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def _encode(data):
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _fernet():
    return Fernet(settings.SECURED_CONVERSATIONS_SECRET_KEY)


def generate_conversation_keypair():
    """Returns the public key, its fingerprint and the Fernet-sealed private key."""

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=RSA_KEY_SIZE,
    )
    public_key = private_key.public_key()
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return (
        _encode(der),
        fingerprint_public_key(public_key),
        _fernet().encrypt(pem).decode('ascii'),
    )


def open_conversation_private_key(sealed_private_key):
    try:
        pem = _fernet().decrypt(sealed_private_key.encode('ascii'))
        return serialization.load_pem_private_key(pem, password=None)
    except (InvalidToken, ValueError, TypeError) as error:
        raise InvalidEncryptedDataError from error


def seal_order_content(fields, public_keys, *, filename='', file=b'', content_type=''):
    """Encrypts the order texts and, optionally, the prescription with one data key."""

    data_key = os.urandom(AES_KEY_SIZE)
    wraps = tuple(_wrap(data_key, public_key) for public_key in public_keys)
    sealed = {
        name: envelope_text(_envelope(plaintext.encode(), data_key, wraps))
        for name, plaintext in fields.items()
        if plaintext
    }
    payload = None
    seal = None
    if file:
        encrypted_file = _envelope(file, data_key, wraps)
        encrypted_name = _envelope(filename.encode(), data_key, wraps)
        payload = decode_base64(encrypted_file.ciphertext)
        seal = {
            'encrypted_filename': encrypted_name.ciphertext,
            'filename_nonce': encrypted_name.nonce,
            'nonce': encrypted_file.nonce,
            'content_type': content_type,
            'wrapped_keys': [
                {
                    'fingerprint': wrapped.fingerprint,
                    'ciphertext': wrapped.ciphertext,
                }
                for wrapped in wraps
            ],
        }
    return sealed, payload, seal


def unwrap_data_key(envelope, private_key):
    """Returns the data key protected by one wrap this private key can open."""

    return _data_key(envelope, private_key)


def open_raw(raw_ciphertext, nonce, private_key, wrapped_keys):
    """Decrypts raw AES-GCM bytes with a wrap this private key can open."""

    data_key = _data_key(
        EncryptedEnvelope(
            ciphertext=_encode(raw_ciphertext),
            nonce=nonce,
            wrapped_keys=tuple(wrapped_keys),
        ),
        private_key,
    )
    return AESGCM(data_key).decrypt(decode_base64(nonce), raw_ciphertext, None)


def open_text(envelope, private_key):
    """Decrypts an envelope with a private key that owns one of its wraps."""

    data_key = _data_key(envelope, private_key)
    opened = AESGCM(data_key).decrypt(
        decode_base64(envelope.nonce),
        decode_base64(envelope.ciphertext),
        None,
    )
    return opened.decode()


def seal_text(plaintext, public_keys):
    """Encrypts text for the given SPKI public keys and returns an envelope."""

    data_key = os.urandom(AES_KEY_SIZE)
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext.encode(), None)
    return EncryptedEnvelope(
        ciphertext=_encode(ciphertext),
        nonce=_encode(nonce),
        wrapped_keys=tuple(_wrap(data_key, public_key) for public_key in public_keys),
    )


def envelope_text(envelope):
    return json.dumps(
        {
            'ciphertext': envelope.ciphertext,
            'nonce': envelope.nonce,
            'wrapped_keys': [
                {
                    'fingerprint': wrapped.fingerprint,
                    'ciphertext': wrapped.ciphertext,
                }
                for wrapped in envelope.wrapped_keys
            ],
        },
        separators=(',', ':'),
    )


def read_envelope(value):
    try:
        data = json.loads(value)
        wrapped_keys = tuple(
            WrappedKey(item['fingerprint'], item['ciphertext'])
            for item in data['wrapped_keys']
        )
    except (TypeError, KeyError, json.JSONDecodeError) as error:
        raise InvalidEncryptedDataError from error
    return EncryptedEnvelope(
        ciphertext=data['ciphertext'],
        nonce=data['nonce'],
        wrapped_keys=wrapped_keys,
    )


def replace_server_wrap(envelope, private_key, server_fingerprint, public_key):
    """Opens the server wrap and adds one device wrap in its place."""

    wrapped = next(
        (
            item
            for item in envelope.wrapped_keys
            if item.fingerprint == server_fingerprint
        ),
        None,
    )
    if wrapped is None:
        return envelope

    data_key = private_key.decrypt(decode_base64(wrapped.ciphertext), _OAEP)
    if len(data_key) != AES_KEY_SIZE:
        raise InvalidEncryptedDataError

    device_wrap = _wrap(data_key, public_key)
    wraps = [
        item for item in envelope.wrapped_keys if item.fingerprint != server_fingerprint
    ]
    if all(item.fingerprint != device_wrap.fingerprint for item in wraps):
        wraps.append(device_wrap)
    return EncryptedEnvelope(
        ciphertext=envelope.ciphertext,
        nonce=envelope.nonce,
        wrapped_keys=tuple(wraps),
    )


def _envelope(plaintext, data_key, wraps):
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, None)
    return EncryptedEnvelope(
        ciphertext=_encode(ciphertext),
        nonce=_encode(nonce),
        wrapped_keys=wraps,
    )


def _data_key(envelope, private_key):
    for wrapped in envelope.wrapped_keys:
        try:
            data_key = private_key.decrypt(decode_base64(wrapped.ciphertext), _OAEP)
        except ValueError:
            continue
        if len(data_key) == AES_KEY_SIZE:
            return data_key
    raise InvalidEncryptedDataError


def _wrap(data_key, public_key):
    key = validate_rsa_public_key(public_key)
    ciphertext = key.encrypt(data_key, _OAEP)
    return WrappedKey(fingerprint_public_key(key), _encode(ciphertext))
