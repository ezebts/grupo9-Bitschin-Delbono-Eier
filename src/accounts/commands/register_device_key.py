from dataclasses import dataclass

from django.db import transaction

from accounts.exceptions import DeviceKeyBelongsToAnotherUserError
from accounts.models import DeviceKey
from shared.encryption import fingerprint_public_key


@dataclass(frozen=True)
class RegisterDeviceKeyParams:
    public_key: str


@transaction.atomic
def register_device_key(user_id, params: RegisterDeviceKeyParams):
    """Adds the public key of one of the user's devices, only once."""

    device_key, _ = DeviceKey.objects.get_or_create(
        fingerprint=fingerprint_public_key(params.public_key),
        defaults={'user_id': user_id, 'public_key': params.public_key},
    )

    if device_key.user_id != user_id:
        raise DeviceKeyBelongsToAnotherUserError

    return device_key
