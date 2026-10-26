import pytest

from accounts.commands.register_device_key import (
    RegisterDeviceKeyParams,
    register_device_key,
)
from accounts.models import DeviceKey, User
from shared.tests.encryption import generate_device_public_key

pytestmark = pytest.mark.django_db


def test_registering_an_existing_key_does_not_duplicate_it():
    public_key, fingerprint = generate_device_public_key()
    user = User.objects.create_user(username='ana@example.com')

    first = register_device_key(user.id, RegisterDeviceKeyParams(public_key))
    again = register_device_key(user.id, RegisterDeviceKeyParams(public_key))

    assert first == again
    assert list(DeviceKey.objects.values_list('fingerprint', flat=True)) == [
        fingerprint,
    ]
