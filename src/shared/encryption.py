import base64
import binascii
import hashlib
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

RSA_KEY_SIZE = 3072
AES_KEY_SIZE = 32
AES_NONCE_SIZE = 12
PASSWORD_SALT_SIZE = 16
PASSWORD_ITERATIONS = 600_000
ENCRYPTION_SIDES = frozenset({'customer', 'pharmacy'})


def _raise_value_error(message, cause=None):
    if cause is not None:
        raise ValueError(message) from cause
    raise ValueError(message)


def _raise_type_error(message):
    raise TypeError(message)


@dataclass(frozen=True)
class WrappedKey:
    fingerprint: str
    ciphertext: str


@dataclass(frozen=True)
class TemporaryWrappedKey:
    side: str
    ciphertext: str
    salt: str
    nonce: str

    def __post_init__(self):
        if self.side not in ENCRYPTION_SIDES:
            _raise_value_error('The temporary key side must be customer or pharmacy.')


@dataclass(frozen=True)
class EncryptedEnvelope:
    ciphertext: str
    nonce: str
    wrapped_keys: tuple[WrappedKey, ...]
    temporary_wrapped_keys: tuple[TemporaryWrappedKey, ...] = ()

    def __post_init__(self):
        if not self.wrapped_keys and not self.temporary_wrapped_keys:
            _raise_value_error('An encrypted envelope must wrap its data key.')
        fingerprints = [wrapped.fingerprint for wrapped in self.wrapped_keys]
        if len(fingerprints) != len(set(fingerprints)):
            _raise_value_error('A device key can only wrap an envelope once.')
        sides = [wrapped.side for wrapped in self.temporary_wrapped_keys]
        if len(sides) != len(set(sides)):
            _raise_value_error(
                'An envelope can only have one temporary key per side.',
            )


@dataclass(frozen=True)
class EncryptedAttachmentMetadata:
    encrypted_filename: str
    filename_nonce: str
    nonce: str
    content_type: str
    size: int

    def __post_init__(self):
        if self.size < 0:
            _raise_value_error('The encrypted attachment size cannot be negative.')


def _decode_base64(value):
    if not isinstance(value, str):
        _raise_type_error('Encrypted values must be base64url strings.')
    try:
        return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    except (ValueError, binascii.Error) as error:
        _raise_value_error('Invalid base64url value.', error)


def _encode_base64(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _load_public_key(public_key):
    if isinstance(public_key, rsa.RSAPublicKey):
        key = public_key
    else:
        if isinstance(public_key, str):
            public_key = public_key.encode('ascii')
        try:
            if b'-----BEGIN' in public_key:
                key = serialization.load_pem_public_key(public_key)
            else:
                key = serialization.load_der_public_key(
                    _decode_base64(
                        public_key.decode('ascii'),
                    )
                )
        except (ValueError, TypeError, UnicodeDecodeError) as error:
            _raise_value_error('The public key must be valid RSA-3072 SPKI.', error)

    if not isinstance(key, rsa.RSAPublicKey) or key.key_size != RSA_KEY_SIZE:
        _raise_value_error('The public key must be RSA-3072.')
    return key


def validate_rsa_public_key(public_key):
    """Validate an RSA-3072 public key and return its cryptography key object."""
    return _load_public_key(public_key)


def fingerprint_public_key(public_key):
    """Return the lowercase hexadecimal SHA-256 fingerprint of the SPKI DER key."""
    key = _load_public_key(public_key)
    der = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def generate_temporary_password():
    return secrets.token_urlsafe(32)


def _derive_temporary_key(password, salt):
    if not isinstance(password, str) or not password:
        _raise_value_error('A non-empty temporary password is required.')
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=PASSWORD_ITERATIONS,
    ).derive(password.encode('utf-8'))


def wrap_data_key(data_key, public_key):
    if len(data_key) != AES_KEY_SIZE:
        _raise_value_error('The data key must be 256 bits.')
    key = _load_public_key(public_key)
    wrapped = key.encrypt(
        data_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return WrappedKey(fingerprint_public_key(key), _encode_base64(wrapped))


def wrap_data_key_with_temporary_password(data_key, password, side):
    if len(data_key) != AES_KEY_SIZE:
        _raise_value_error('The data key must be 256 bits.')
    if side not in ENCRYPTION_SIDES:
        _raise_value_error('The temporary key side must be customer or pharmacy.')
    salt = secrets.token_bytes(PASSWORD_SALT_SIZE)
    nonce = secrets.token_bytes(AES_NONCE_SIZE)
    key = _derive_temporary_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, data_key, None)
    return TemporaryWrappedKey(
        side=side,
        ciphertext=_encode_base64(ciphertext),
        salt=_encode_base64(salt),
        nonce=_encode_base64(nonce),
    )


def unwrap_data_key_with_temporary_password(wrapped_key, password):
    key = _derive_temporary_key(password, _decode_base64(wrapped_key.salt))
    return AESGCM(key).decrypt(
        _decode_base64(wrapped_key.nonce),
        _decode_base64(wrapped_key.ciphertext),
        None,
    )


def rewrap_envelope(envelope, password, public_key, side):
    """Replace a side's temporary data-key wraps with a device public-key wrap."""
    if side not in ENCRYPTION_SIDES:
        _raise_value_error('The temporary key side must be customer or pharmacy.')
    temporary_keys = tuple(
        wrapped for wrapped in envelope.temporary_wrapped_keys if wrapped.side == side
    )
    if not temporary_keys:
        _raise_value_error(f'No temporary key was found for the {side} side.')

    fingerprint = fingerprint_public_key(public_key)
    wrapped_keys = list(envelope.wrapped_keys)
    if not any(wrapped.fingerprint == fingerprint for wrapped in wrapped_keys):
        for temporary_key in temporary_keys:
            data_key = unwrap_data_key_with_temporary_password(
                temporary_key,
                password,
            )
            wrapped_keys.append(wrap_data_key(data_key, public_key))

    remaining_temporary_keys = tuple(
        wrapped for wrapped in envelope.temporary_wrapped_keys if wrapped.side != side
    )
    return EncryptedEnvelope(
        ciphertext=envelope.ciphertext,
        nonce=envelope.nonce,
        wrapped_keys=tuple(wrapped_keys),
        temporary_wrapped_keys=remaining_temporary_keys,
    )
