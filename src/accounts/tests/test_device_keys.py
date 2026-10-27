from http import HTTPStatus

import pytest
from django.urls import reverse

from accounts.commands.register_device import RegisterDeviceParams, register_device
from accounts.models import DeviceKey, User
from shared.tests.encryption import generate_device_public_key

pytestmark = pytest.mark.django_db

PASSWORD = 'una-clave-segura-123'  # noqa: S105


def test_authenticated_user_registers_a_device_key_via_endpoint(client):
    public_key, fingerprint = generate_device_public_key()
    user = User.objects.create_user(
        username='ana@example.com',
        email='ana@example.com',
        password=PASSWORD,
    )
    client.login(username='ana@example.com', password=PASSWORD)

    response = client.post(
        reverse('register_device'),
        {'public_key': public_key},
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert user.device_keys.get().fingerprint == fingerprint


def test_registering_an_existing_key_does_not_duplicate_it():
    public_key, fingerprint = generate_device_public_key()
    user = User.objects.create_user(username='ana@example.com')

    first = register_device(user.id, RegisterDeviceParams(public_key))
    again = register_device(user.id, RegisterDeviceParams(public_key))

    assert first == again
    assert list(DeviceKey.objects.values_list('fingerprint', flat=True)) == [
        fingerprint,
    ]
