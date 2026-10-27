from dataclasses import dataclass

from django.db import transaction

from accounts.exceptions import DeviceKeyBelongsToAnotherUserError
from accounts.models import DeviceKey, PharmacyAccount
from chats.commands.hand_off_conversation import hand_off_pharmacy_conversations
from shared.encryption import fingerprint_public_key


@dataclass(frozen=True)
class RegisterDeviceParams:
    public_key: str


@transaction.atomic
def register_device(user_id, params: RegisterDeviceParams):
    """Adds the public key of one of the user's devices, only once."""

    pharmacy_id = (
        PharmacyAccount.objects.filter(user_id=user_id)
        .values_list(
            'pharmacy_id',
            flat=True,
        )
        .first()
    )
    pharmacy_has_a_device = (
        pharmacy_id is not None
        and DeviceKey.objects.filter(
            user__pharmacy_account__pharmacy_id=pharmacy_id,
        ).exists()
    )
    device_key, _ = DeviceKey.objects.get_or_create(
        fingerprint=fingerprint_public_key(params.public_key),
        defaults={'user_id': user_id, 'public_key': params.public_key},
    )

    if device_key.user_id != user_id:
        raise DeviceKeyBelongsToAnotherUserError

    if pharmacy_id is not None and not pharmacy_has_a_device:
        hand_off_pharmacy_conversations(pharmacy_id, params.public_key)

    return device_key
