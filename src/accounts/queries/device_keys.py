from dataclasses import dataclass

from accounts.models import DeviceKey
from shared.encryption import fingerprint_public_key


@dataclass(frozen=True)
class PublicDeviceKey:
    user_id: int
    public_key: str
    fingerprint: str


def get_user_device_keys(user_id):
    return tuple(
        PublicDeviceKey(
            user_id=device_key.user_id,
            public_key=device_key.public_key,
            fingerprint=device_key.fingerprint,
        )
        for device_key in DeviceKey.objects.filter(user_id=user_id)
    )


def get_pharmacy_device_keys(pharmacy_id):
    return tuple(
        PublicDeviceKey(
            user_id=device_key.user_id,
            public_key=device_key.public_key,
            fingerprint=device_key.fingerprint,
        )
        for device_key in DeviceKey.objects.filter(
            user__pharmacy_account__pharmacy_id=pharmacy_id,
        )
    )


def is_device_key_registered(public_key):
    return DeviceKey.objects.filter(
        fingerprint=fingerprint_public_key(public_key),
    ).exists()
