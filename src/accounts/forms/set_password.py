from django import forms
from django.contrib.auth.password_validation import validate_password


class SetPasswordForm(forms.Form):
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput)

    password2 = forms.CharField(
        label='Repetí la contraseña',
        widget=forms.PasswordInput,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password1(self):
        password1 = self.cleaned_data['password1']
        validate_password(password1, self.user)
        return password1

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Las contraseñas no coinciden.')

        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data['password1'])
        self.user.save(update_fields=['password'])
        return self.user
