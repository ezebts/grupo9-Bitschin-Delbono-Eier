from django import forms
from django.utils import timezone

from orders.commands.save_quote import QuoteTerms
from orders.models import DeliveryPreference
from shared.forms import TypedForm


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


class QuoteForm(TypedForm[QuoteTerms]):
    price = forms.DecimalField(
        label='Precio de la preparación (ARS)',
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
    )

    preparation_time = forms.CharField(
        label='Lista en',
        max_length=80,
        widget=forms.TextInput(attrs={'placeholder': 'Por ejemplo: 48 h hábiles'}),
    )

    delivery_preferences = forms.MultipleChoiceField(
        label='Modalidad de entrega',
        choices=(),
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'checkbox checkbox-primary'},
        ),
    )

    delivery_cost = forms.DecimalField(
        label='Costo de envío (ARS)',
        max_digits=12,
        decimal_places=2,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
    )

    valid_until = forms.DateField(
        label='Válido hasta',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, delivery_options=(), **kwargs):
        super().__init__(*args, **kwargs)
        allowed = set(delivery_options)
        self.fields['delivery_preferences'].choices = tuple(
            (value, label)
            for value, label in DeliveryPreference.choices
            if value in allowed
        )

    def clean_preparation_time(self):
        return self.cleaned_data['preparation_time'].strip()

    def clean(self):
        cleaned = super().clean()
        valid_until = cleaned.get('valid_until')
        if valid_until and valid_until < timezone.localdate():
            self.add_error(
                'valid_until',
                'La fecha de vencimiento no puede estar en el pasado.',
            )
        if (
            DeliveryPreference.HOME_DELIVERY
            not in cleaned.get('delivery_preferences', ())
            and cleaned.get('delivery_cost', 0) != 0
        ):
            self.add_error(
                'delivery_cost',
                'El retiro en farmacia no puede tener costo de envío.',
            )
        return cleaned

    @property
    def cleaned_params(self) -> QuoteTerms:
        data = self.cleaned_data
        return QuoteTerms(
            price=data['price'],
            preparation_time=data['preparation_time'],
            delivery_preferences=tuple(data['delivery_preferences']),
            delivery_cost=data['delivery_cost'],
            valid_until=data['valid_until'],
        )
