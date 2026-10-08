from django import forms

from .models import User


class SignupForm(forms.Form):
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
