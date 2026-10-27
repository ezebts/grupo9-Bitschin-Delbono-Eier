from django import forms
from django.core.validators import DecimalValidator

from orders.commands.advance_order import AdvanceOrderParams
from orders.commands.submit_quote import SubmitQuoteParams
from orders.models import DeliveryPreference
from shared.forms import TypedForm
from shared.values import InvalidMoneyError, Money

CURRENCY_CHOICES = [(currency, currency.value) for currency in Money.Currency]

PREPARATION_TIME_CHOICES = (
    ('24 h hábiles', '24 h hábiles'),
    ('48 h hábiles', '48 h hábiles'),
    ('72 h hábiles', '72 h hábiles'),
    ('5 días hábiles', '5 días hábiles'),
)


class CustomerMessageForm(forms.Form):
    message = forms.CharField(
        max_length=100000,
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
        max_length=100000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'placeholder': 'Escribí un mensaje al cliente…',
                'maxlength': 2000,
            },
        ),
    )


class ChatQuoteForm(TypedForm[SubmitQuoteParams]):
    price_currency = forms.ChoiceField(
        label='Moneda del precio',
        choices=CURRENCY_CHOICES,
        initial=Money.ARS().currency,
    )

    price = forms.DecimalField(
        label='Precio total',
        localize=True,
    )

    preparation_time = forms.ChoiceField(
        label='Lista en',
        choices=PREPARATION_TIME_CHOICES,
        initial='48 h hábiles',
    )

    delivery_preferences = forms.MultipleChoiceField(
        label='Entrega',
        choices=(),
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'checkbox checkbox-primary'},
        ),
    )

    delivery_cost_currency = forms.ChoiceField(
        label='Moneda del costo de envío',
        choices=CURRENCY_CHOICES,
        initial=Money.ARS().currency,
    )

    delivery_cost = forms.DecimalField(
        label='Costo de envío',
        localize=True,
        required=False,
    )

    valid_until = forms.DateField(
        label='Válido hasta',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )

    def __init__(self, *args, delivery_options=(), **kwargs):
        super().__init__(*args, **kwargs)
        allowed = set(delivery_options)
        self.fields['delivery_preferences'].choices = tuple(
            (value, label)
            for value, label in DeliveryPreference.choices
            if value in allowed
        )
        self._blank_delivery_cost_without_home_delivery()
        self._configure_money_field('price', 'price_currency')
        self._configure_money_field('delivery_cost', 'delivery_cost_currency')

    def _blank_delivery_cost_without_home_delivery(self):
        if self.is_bound:
            if hasattr(self.data, 'getlist'):
                selected = self.data.getlist('delivery_preferences')
            else:
                selected = self.data.get('delivery_preferences') or ()
            if DeliveryPreference.HOME_DELIVERY in selected:
                return
            data = self.data.copy()
            data['delivery_cost'] = ''
            self.data = data
            return

        initial = dict(self.initial or {})
        preferences = initial.get('delivery_preferences') or ()
        if DeliveryPreference.HOME_DELIVERY in preferences:
            return
        initial['delivery_cost'] = None
        self.initial = initial

    def _money_for_field(self, currency_field):
        source = self.data if self.is_bound else self.initial
        currency = source.get(currency_field) if source else None

        if not currency:
            return Money.ARS()

        return Money.create(currency)

    def _configure_money_field(self, amount_field, currency_field):
        money = self._money_for_field(currency_field)
        field = self.fields[amount_field]
        field.decimal_places = money.decimal_places
        field.max_digits = money.max_digits
        for validator in field.validators:
            if isinstance(validator, DecimalValidator):
                validator.decimal_places = money.decimal_places
                validator.max_digits = money.max_digits

    def _validate_money_amount(self, cleaned, amount_field, currency_field):
        amount = cleaned.get(amount_field)
        currency = cleaned.get(currency_field)

        if amount is None or not currency:
            return

        try:
            Money.create(currency, amount)
        except InvalidMoneyError as error:
            self.add_error(amount_field, error.message)

    def clean(self):
        cleaned = super().clean()

        self._validate_money_amount(cleaned, 'price', 'price_currency')

        self._validate_money_amount(
            cleaned,
            'delivery_cost',
            'delivery_cost_currency',
        )

        delivery_cost = cleaned.get('delivery_cost')

        if (
            DeliveryPreference.HOME_DELIVERY
            not in cleaned.get('delivery_preferences', ())
            and delivery_cost
        ):
            self.add_error(
                'delivery_cost',
                'El retiro en farmacia no puede tener costo de envío.',
            )

        return cleaned

    @property
    def cleaned_params(self) -> SubmitQuoteParams:
        data = self.cleaned_data
        delivery_amount = data.get('delivery_cost')

        if delivery_amount is None:
            delivery_amount = 0

        return SubmitQuoteParams(
            price=Money.create(data['price_currency'], data['price']),
            preparation_time=data['preparation_time'],
            delivery_preferences=tuple(data['delivery_preferences']),
            delivery_cost=Money.create(
                data['delivery_cost_currency'],
                delivery_amount,
            ),
            valid_until=data['valid_until'],
        )


class OrderStatusForm(TypedForm[AdvanceOrderParams]):
    estimated_at = forms.DateField(
        label='Fecha estimada',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )

    @property
    def cleaned_params(self) -> AdvanceOrderParams:
        return AdvanceOrderParams(estimated_at=self.cleaned_data['estimated_at'])
