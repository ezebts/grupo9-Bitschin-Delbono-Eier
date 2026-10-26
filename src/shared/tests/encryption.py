import base64
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_device_public_key():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=3072,
    )
    public_key = private_key.public_key()
    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_key_base64 = (
        base64.urlsafe_b64encode(public_key_der)
        .decode('ascii')
        .rstrip(
            '=',
        )
    )
    fingerprint = hashlib.sha256(public_key_der).hexdigest()
    return public_key_base64, fingerprint
