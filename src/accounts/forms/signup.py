from django import forms

from accounts.commands.signup import signup, signup_with_invitation
from accounts.exceptions import InvalidInvitationLinkError
from accounts.models import InvitationLink, User


class SignupForm(forms.Form):
    role = forms.ChoiceField(
        label='¿Cómo vas a usar la app?',
        choices=User.Role.choices,
        widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'}),
    )

    first_name = forms.CharField(label='Nombre', max_length=150)

    last_name = forms.CharField(label='Apellido', max_length=150)

    invitation_link = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_invitation_link(self):
        raw = (self.cleaned_data.get('invitation_link') or '').strip()

        if not raw:
            return None

        try:
            return InvitationLink.from_value(raw)
        except InvalidInvitationLinkError as error:
            raise forms.ValidationError(error.message) from None

    def clean(self):
        cleaned = super().clean()
        invitation = cleaned.get('invitation_link')
        if not invitation:
            return cleaned

        email = (cleaned.get('email') or '').lower()
        if email and email != invitation.email.lower():
            self.add_error(None, 'El email no coincide con la invitación.')

        if cleaned.get('role') and cleaned['role'] != invitation.role:
            self.add_error(None, 'El rol no coincide con la invitación.')

        return cleaned

    def signup(self, _request, user):

        invitation = self.cleaned_data.get('invitation_link')

        if invitation:
            signup_with_invitation(user, invitation)
            return

        signup(user, self.cleaned_data['role'])
