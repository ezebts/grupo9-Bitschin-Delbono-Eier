from django import forms

from .models import User


class SignupForm(forms.Form):
    """Extra signup fields, used by allauth for both email and Google signups.

    allauth already saves first_name, last_name and email; we only add the role.
    """

    role = forms.ChoiceField(
        label='¿Cómo vas a usar la app?',
        choices=User.Role.choices,
        widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'}),
    )
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)

    def signup(self, _request, user):
        user.role = self.cleaned_data['role']
        user.save(update_fields=['role'])
