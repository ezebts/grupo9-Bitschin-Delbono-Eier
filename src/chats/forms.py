from django import forms


class InquiryForm(forms.Form):
    customer_phone = forms.CharField(
        label='Teléfono (opcional)',
        max_length=40,
        required=False,
        widget=forms.TelInput(attrs={'autocomplete': 'tel'}),
    )
    subject = forms.CharField(
        label='¿En qué podemos ayudarte?',
        max_length=200,
    )
    message = forms.CharField(
        label='Tu consulta',
        max_length=2000,
        widget=forms.Textarea(attrs={'rows': 5}),
    )


class CustomerMessageForm(forms.Form):
    message = forms.CharField(
        max_length=2000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'placeholder': 'Escribí tu respuesta...',
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
                'rows': 1,
                'placeholder': 'Escribí un mensaje...',
                'maxlength': 2000,
            },
        ),
    )
