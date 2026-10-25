import base64
import binascii
import hashlib
import re
import secrets
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.utils.translation import gettext_lazy as _

from shared.exceptions import Error

RSA_KEY_SIZE = 3072
RSA_CIPHERTEXT_SIZE = RSA_KEY_SIZE // 8
AES_KEY_SIZE = 32
AES_NONCE_SIZE = 12
AES_GCM_TAG_SIZE = 16
PASSWORD_SALT_SIZE = 16
PASSWORD_ITERATIONS = 600_000
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
        if len(_decode_base64(self.salt)) != PASSWORD_SALT_SIZE:
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


def _encode_base64(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


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


def generate_temporary_password():
    return secrets.token_urlsafe(32)


def _derive_temporary_key(password, salt):
    if not isinstance(password, str) or not password:
        raise InvalidEncryptedDataError
    if not isinstance(salt, bytes) or len(salt) != PASSWORD_SALT_SIZE:
        raise InvalidEncryptedDataError
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=PASSWORD_ITERATIONS,
    ).derive(password.encode('utf-8'))


def wrap_data_key(data_key, public_key):
    if not isinstance(data_key, bytes) or len(data_key) != AES_KEY_SIZE:
        raise InvalidEncryptedDataError
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
    if not isinstance(data_key, bytes) or len(data_key) != AES_KEY_SIZE:
        raise InvalidEncryptedDataError
    if not isinstance(side, str) or side not in ENCRYPTION_SIDES:
        raise InvalidEncryptedDataError
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
    try:
        key = _derive_temporary_key(password, _decode_base64(wrapped_key.salt))
        return AESGCM(key).decrypt(
            _decode_base64(wrapped_key.nonce),
            _decode_base64(wrapped_key.ciphertext),
            None,
        )
    except InvalidTag as error:
        raise InvalidEncryptedDataError from error


def rewrap_envelope(envelope, password, public_key, side):
    """Replace a side's temporary data-key wraps with a device public-key wrap."""
    if not isinstance(envelope, EncryptedEnvelope):
        raise InvalidEncryptedDataError
    if not isinstance(side, str) or side not in ENCRYPTION_SIDES:
        raise InvalidEncryptedDataError
    temporary_keys = tuple(
        wrapped for wrapped in envelope.temporary_wrapped_keys if wrapped.side == side
    )
    if not temporary_keys:
        raise InvalidEncryptedDataError

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
