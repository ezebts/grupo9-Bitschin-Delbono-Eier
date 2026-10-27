from django import forms

from accounts.commands.register_device import RegisterDeviceParams
from shared.encryption import validate_rsa_public_key
from shared.forms import TypedForm


class DeviceKeyForm(TypedForm[RegisterDeviceParams]):
    """Public key of a browser that is already signed in."""

    public_key = forms.CharField(widget=forms.HiddenInput())

    def clean_public_key(self):
        public_key = self.cleaned_data['public_key']
        validate_rsa_public_key(public_key)
        return public_key

    @property
    def cleaned_params(self) -> RegisterDeviceParams:
        return RegisterDeviceParams(public_key=self.cleaned_data['public_key'])
