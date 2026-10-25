import base64
import binascii
import hashlib
import re
from dataclasses import dataclass

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.utils.translation import gettext_lazy as _

from shared.exceptions import Error

RSA_KEY_SIZE = 3072
RSA_CIPHERTEXT_SIZE = RSA_KEY_SIZE // 8
AES_KEY_SIZE = 32
AES_NONCE_SIZE = 12
AES_GCM_TAG_SIZE = 16
TEMPORARY_SALT_SIZE = 16
ENCRYPTION_SIDES = frozenset({'customer', 'pharmacy'})


@dataclass(frozen=True)
class InvalidEncryptedDataError(Error):
    message = _('Los datos cifrados no son válidos.')


@dataclass(frozen=True)
class InvalidPublicKeyError(Error):
    message = _('La clave pública del dispositivo no es válida.')


@dataclass(frozen=True)
class WrappedKey:
    fingerprint: str
    ciphertext: str

    def __post_init__(self):
        if not isinstance(self.fingerprint, str) or not re.fullmatch(
            r'[0-9a-fA-F]{64}',
            self.fingerprint,
        ):
            raise InvalidEncryptedDataError
        object.__setattr__(self, 'fingerprint', self.fingerprint.lower())
        if len(_decode_base64(self.ciphertext)) != RSA_CIPHERTEXT_SIZE:
            raise InvalidEncryptedDataError


@dataclass(frozen=True)
class TemporaryWrappedKey:
    side: str
    ciphertext: str
    salt: str
    nonce: str

    def __post_init__(self):
        if not isinstance(self.side, str) or self.side not in ENCRYPTION_SIDES:
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.ciphertext)) != AES_KEY_SIZE + 16:
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.salt)) != TEMPORARY_SALT_SIZE:
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.nonce)) != AES_NONCE_SIZE:
            raise InvalidEncryptedDataError


@dataclass(frozen=True)
class EncryptedEnvelope:
    ciphertext: str
    nonce: str
    wrapped_keys: tuple[WrappedKey, ...]
    temporary_wrapped_keys: tuple[TemporaryWrappedKey, ...] = ()

    def __post_init__(self):
        if not isinstance(self.wrapped_keys, tuple) or not isinstance(
            self.temporary_wrapped_keys,
            tuple,
        ):
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.ciphertext)) < AES_GCM_TAG_SIZE:
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.nonce)) != AES_NONCE_SIZE:
            raise InvalidEncryptedDataError
        if not all(isinstance(wrapped, WrappedKey) for wrapped in self.wrapped_keys):
            raise InvalidEncryptedDataError
        if not all(
            isinstance(wrapped, TemporaryWrappedKey)
            for wrapped in self.temporary_wrapped_keys
        ):
            raise InvalidEncryptedDataError
        if not self.wrapped_keys and not self.temporary_wrapped_keys:
            raise InvalidEncryptedDataError
        fingerprints = [wrapped.fingerprint.lower() for wrapped in self.wrapped_keys]
        if len(fingerprints) != len(set(fingerprints)):
            raise InvalidEncryptedDataError
        sides = [wrapped.side for wrapped in self.temporary_wrapped_keys]
        if len(sides) != len(set(sides)):
            raise InvalidEncryptedDataError


@dataclass(frozen=True)
class EncryptedAttachmentMetadata:
    encrypted_filename: str
    filename_nonce: str
    nonce: str
    content_type: str
    size: int

    def __post_init__(self):
        if (
            not isinstance(self.size, int)
            or isinstance(self.size, bool)
            or self.size < 0
        ):
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.encrypted_filename)) < AES_GCM_TAG_SIZE:
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.filename_nonce)) != AES_NONCE_SIZE:
            raise InvalidEncryptedDataError
        if len(_decode_base64(self.nonce)) != AES_NONCE_SIZE:
            raise InvalidEncryptedDataError


def _decode_base64(value):
    if not isinstance(value, str) or not re.fullmatch(
        r'[A-Za-z0-9_-]*={0,2}',
        value,
    ):
        raise InvalidEncryptedDataError
    unpadded = value.rstrip('=')
    expected_padding = '=' * (-len(unpadded) % 4)
    if len(unpadded) % 4 == 1 or value[len(unpadded) :] not in ('', expected_padding):
        raise InvalidEncryptedDataError
    try:
        return base64.b64decode(
            unpadded + expected_padding,
            altchars=b'-_',
            validate=True,
        )
    except (ValueError, binascii.Error) as error:
        raise InvalidEncryptedDataError from error


def _load_public_key(public_key):
    if isinstance(public_key, rsa.RSAPublicKey):
        key = public_key
    else:
        if isinstance(public_key, str):
            try:
                public_key = public_key.encode('ascii')
            except UnicodeEncodeError as error:
                raise InvalidPublicKeyError from error
        if not isinstance(public_key, bytes):
            raise InvalidPublicKeyError
        try:
            if b'-----BEGIN' in public_key:
                key = serialization.load_pem_public_key(public_key)
            else:
                key = serialization.load_der_public_key(
                    _decode_base64(
                        public_key.decode('ascii'),
                    )
                )
        except (
            InvalidEncryptedDataError,
            ValueError,
            TypeError,
            UnicodeDecodeError,
            UnsupportedAlgorithm,
        ) as error:
            raise InvalidPublicKeyError from error

    if not isinstance(key, rsa.RSAPublicKey) or key.key_size != RSA_KEY_SIZE:
        raise InvalidPublicKeyError
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
