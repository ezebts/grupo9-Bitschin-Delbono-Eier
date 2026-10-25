import base64
import hashlib
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from shared.encryption import (
    AES_KEY_SIZE,
    AES_NONCE_SIZE,
    PASSWORD_ITERATIONS,
    PASSWORD_SALT_SIZE,
    EncryptedEnvelope,
    TemporaryWrappedKey,
    WrappedKey,
)


def _raise_value_error(message):
    raise ValueError(message)


def _raise_type_error(message):
    raise TypeError(message)


def _encode_base64(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _decode_base64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def generate_device_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=3072,
    )
    public_key = private_key.public_key()
    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_key_base64 = _encode_base64(public_key_der)
    fingerprint = hashlib.sha256(public_key_der).hexdigest()
    return private_key, public_key_base64, fingerprint


def _derive_temporary_key(password, salt):
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=PASSWORD_ITERATIONS,
    ).derive(password.encode('utf-8'))


def encrypt_message(plaintext, public_keys=(), temporary_passwords=()):
    data_key = secrets.token_bytes(AES_KEY_SIZE)
    nonce = secrets.token_bytes(AES_NONCE_SIZE)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext.encode('utf-8'), None)
    wrapped_keys = []
    for recipient in public_keys:
        if isinstance(recipient, tuple):
            public_key, fingerprint = recipient
        else:
            public_key = recipient
            fingerprint = None
        if isinstance(public_key, str):
            public_key = serialization.load_der_public_key(
                _decode_base64(public_key),
            )
        if not isinstance(public_key, rsa.RSAPublicKey):
            _raise_type_error('Expected an RSA public key.')
        der = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        wrapped = public_key.encrypt(
            data_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        wrapped_keys.append(
            WrappedKey(
                fingerprint or hashlib.sha256(der).hexdigest(), _encode_base64(wrapped)
            ),
        )

    temporary_wrapped_keys = []
    for side, password in temporary_passwords:
        salt = secrets.token_bytes(PASSWORD_SALT_SIZE)
        key = _derive_temporary_key(password, salt)
        wrap_nonce = secrets.token_bytes(AES_NONCE_SIZE)
        wrapped = AESGCM(key).encrypt(wrap_nonce, data_key, None)
        temporary_wrapped_keys.append(
            TemporaryWrappedKey(
                side=side,
                ciphertext=_encode_base64(wrapped),
                salt=_encode_base64(salt),
                nonce=_encode_base64(wrap_nonce),
            ),
        )

    return EncryptedEnvelope(
        ciphertext=_encode_base64(ciphertext),
        nonce=_encode_base64(nonce),
        wrapped_keys=tuple(wrapped_keys),
        temporary_wrapped_keys=tuple(temporary_wrapped_keys),
    )


def decrypt_message(
    envelope,
    private_key=None,
    fingerprint=None,
    temporary_password=None,
    side=None,
):
    if temporary_password is not None:
        wrapped_key = next(
            key for key in envelope.temporary_wrapped_keys if key.side == side
        )
        data_key = AESGCM(
            _derive_temporary_key(
                temporary_password,
                _decode_base64(wrapped_key.salt),
            ),
        ).decrypt(
            _decode_base64(wrapped_key.nonce),
            _decode_base64(wrapped_key.ciphertext),
            None,
        )
    else:
        if private_key is None or fingerprint is None:
            _raise_value_error(
                'A device private key and fingerprint are required.',
            )
        wrapped_key = next(
            key for key in envelope.wrapped_keys if key.fingerprint == fingerprint
        )
        data_key = private_key.decrypt(
            _decode_base64(wrapped_key.ciphertext),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    plaintext = AESGCM(data_key).decrypt(
        _decode_base64(envelope.nonce),
        _decode_base64(envelope.ciphertext),
        None,
    )
    return plaintext.decode('utf-8')
