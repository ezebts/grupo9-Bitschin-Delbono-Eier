from django import forms


class CustomerMessageForm(forms.Form):
    message = forms.CharField(
        max_length=2000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'placeholder': 'Escribí un mensaje a la farmacia…',
                'maxlength': 2000,
            },
        ),
    )


class MessageForm(forms.Form):
    message = forms.CharField(
        max_length=2000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'placeholder': 'Escribí un mensaje al cliente…',
                'maxlength': 2000,
            },
        ),
    )
