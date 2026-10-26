from django import forms

from accounts.commands.register_device_key import RegisterDeviceKeyParams
from accounts.queries.device_keys import is_device_key_registered
from shared.encryption import validate_rsa_public_key
from shared.forms import TypedForm


class DeviceKeyForm(TypedForm[RegisterDeviceKeyParams]):
    """Public key of a browser that is already signed in."""

    public_key = forms.CharField(
        widget=forms.HiddenInput(attrs={'data-e2ee-public-key': ''}),
    )

    def clean_public_key(self):
        public_key = self.cleaned_data['public_key']
        validate_rsa_public_key(public_key)
        return public_key

    @property
    def cleaned_params(self) -> RegisterDeviceKeyParams:
        return RegisterDeviceKeyParams(public_key=self.cleaned_data['public_key'])


class EncryptionKeysForm(DeviceKeyForm):
    """Public key of the browser that opens a new account, when it could make one."""

    public_key = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'data-e2ee-public-key': ''}),
    )

    def clean_public_key(self):
        public_key = self.cleaned_data['public_key']
        if not public_key:
            return public_key

        super().clean_public_key()
        # A new account can't take a key that is already registered: the account
        # opens without it and the browser registers another one after signup.
        if is_device_key_registered(public_key):
            return ''

        return public_key
