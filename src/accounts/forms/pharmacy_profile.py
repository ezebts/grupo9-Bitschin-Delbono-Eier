from django import forms
from django.core.validators import DecimalValidator

from accounts.commands.update_pharmacy_profile import UpdatePharmacyProfileParams
from accounts.models import (
    Cuit,
    DeliveryRadius,
    DeliveryTerms,
    OpeningHours,
    PharmacyKind,
    PreparationTag,
)
from accounts.queries.pharmacy_profile import PharmacyAccountProfile
from shared.forms import TypedForm
from shared.values import InvalidTimeSlotError, Location, Money, PhoneNumber, TimeSlot


class PharmacyDetailsForm(TypedForm):
    visible = forms.BooleanField(label='Visible en la búsqueda', required=False)

    kind = forms.ChoiceField(
        label='Tipo',
        choices=PharmacyKind.choices,
        widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'}),
    )

    trade_name = forms.CharField(label='Nombre comercial', max_length=150)

    legal_name = forms.CharField(label='Razón social', max_length=150)

    cuit = forms.CharField(label='CUIT', max_length=13)

    technical_director = forms.CharField(label='Director técnico', max_length=150)

    license = forms.CharField(label='Matrícula', max_length=40)

    request_email = forms.EmailField(
        label='Email para solicitudes',
        help_text='Acá llega cada solicitud nueva y cada mensaje de un cliente.',
    )

    phone = forms.CharField(label='Teléfono', max_length=30)

    website = forms.URLField(label='Sitio web', required=False, assume_scheme='https')

    address = forms.CharField(label='Dirección', max_length=200)

    locality = forms.CharField(label='Localidad', max_length=120)

    postal_code = forms.CharField(
        label='Código postal',
        max_length=Location.postal_code_max_length,
    )

    def clean_trade_name(self):
        return self.cleaned_data['trade_name'].strip()

    def clean_legal_name(self):
        return self.cleaned_data['legal_name'].strip()

    def clean_cuit(self):
        return Cuit.create(self.cleaned_data['cuit'])

    def clean_technical_director(self):
        return self.cleaned_data['technical_director'].strip()

    def clean_license(self):
        return self.cleaned_data['license'].strip()

    def clean_phone(self):
        return PhoneNumber.AR(self.cleaned_data['phone'])

    def clean_website(self):
        return (self.cleaned_data.get('website') or '').strip()

    def _clean_location(self, cleaned):
        location_fields = ('address', 'locality', 'postal_code')
        if not all(field in cleaned for field in location_fields):
            return

        cleaned['location'] = Location.create(
            cleaned['address'],
            cleaned['locality'],
            cleaned['postal_code'],
        )

    @classmethod
    def _details_initial(cls, profile):
        return {
            'visible': profile.visible,
            'kind': profile.kind,
            'trade_name': profile.trade_name,
            'legal_name': profile.legal_name,
            'cuit': profile.cuit.number if profile.cuit else '',
            'technical_director': profile.technical_director,
            'license': profile.license,
            'request_email': profile.request_email,
            'phone': profile.phone.number if profile.phone else '',
            'website': profile.website,
            'address': profile.location.address if profile.location else '',
            'locality': profile.location.locality if profile.location else '',
            'postal_code': profile.location.postal_code if profile.location else '',
        }


class PharmacyServiceForm(TypedForm):
    day_labels = (
        (OpeningHours.weekday, 'Lun a vie'),
        (OpeningHours.saturday, 'Sábados'),
        (OpeningHours.sunday, 'Dom y feriados'),
    )

    day_defaults = (
        (OpeningHours.weekday, False),
        (OpeningHours.saturday, False),
        (OpeningHours.sunday, True),
    )

    pickup = forms.BooleanField(label='Retiro en el local', required=False)

    home_delivery = forms.BooleanField(label='Envío a domicilio', required=False)

    delivery_radius = forms.TypedChoiceField(
        label='Hasta',
        required=False,
        coerce=int,
        choices=[
            ('', '—'),
            *[(radius.value, f'{radius.value} km') for radius in DeliveryRadius],
        ],
        empty_value=None,
    )

    delivery_currency = forms.ChoiceField(
        label='Moneda',
        required=False,
        choices=[(currency, currency.value) for currency in Money.Currency],
        initial=Money.ARS().currency,
    )

    delivery_base_cost = forms.DecimalField(
        label='Costo base de envío',
        required=False,
    )

    preparation_tags = forms.MultipleChoiceField(
        label='Preparaciones que realizás',
        choices=PreparationTag.choices,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'checkbox checkbox-primary'},
        ),
        help_text='Se usan para los filtros del mapa.',
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self._configure_delivery_cost()

        for day, label in self.day_labels:
            self.fields[f'{day}_closed'] = forms.BooleanField(
                label=f'{label}: cerrado',
                required=False,
            )

            self.fields[f'{day}_opens'] = forms.TimeField(
                label=f'{label}: abre',
                required=False,
                widget=forms.TimeInput(attrs={'type': 'time'}),
            )

            self.fields[f'{day}_closes'] = forms.TimeField(
                label=f'{label}: cierra',
                required=False,
                widget=forms.TimeInput(attrs={'type': 'time'}),
            )

            self._validate_opening_ranges(day)

    def _configure_delivery_cost(self):
        money = self._money_for_selected_currency()
        field = self.fields['delivery_base_cost']
        field.decimal_places = money.decimal_places
        field.max_digits = money.max_digits

        for validator in field.validators:
            if isinstance(validator, DecimalValidator):
                validator.decimal_places = money.decimal_places
                validator.max_digits = money.max_digits

    def _money_for_selected_currency(self):
        source = self.data if self.is_bound else self.initial
        currency = source.get('delivery_currency') if source else None

        if not currency:
            return Money.ARS()

        return Money.create(currency)

    def clean_delivery_base_cost(self):
        amount = self.cleaned_data['delivery_base_cost']

        if amount is None:
            return None

        Money.create(self.cleaned_data['delivery_currency'], amount)

        return amount

    def clean_preparation_tags(self):
        return {PreparationTag(tag) for tag in self.cleaned_data['preparation_tags']}

    def _validate_opening_ranges(self, day):
        def clean_opens():
            return self._validate_opens(day)

        def clean_closes():
            return self._validate_closes(day)

        setattr(self, f'clean_{day}_opens', clean_opens)
        setattr(self, f'clean_{day}_closes', clean_closes)

    def _validate_opens(self, day):
        opens = self.cleaned_data[f'{day}_opens']

        if self.cleaned_data.get(f'{day}_closed') or opens is not None:
            return opens

        raise InvalidTimeSlotError

    def _validate_closes(self, day):
        closes = self.cleaned_data[f'{day}_closes']

        if self.cleaned_data.get(f'{day}_closed'):
            return closes

        opens_key = f'{day}_opens'
        if opens_key not in self.cleaned_data:
            if closes is None:
                raise InvalidTimeSlotError
            return closes

        TimeSlot.create(
            name=day,
            opens=self.cleaned_data[opens_key],
            closes=closes,
        )

        return closes

    def _clean_opening_hours(self, cleaned):
        slots = []
        for day in OpeningHours.days:
            closed_key = f'{day}_closed'
            opens_key = f'{day}_opens'
            closes_key = f'{day}_closes'
            day_fields = (closed_key, opens_key, closes_key)
            if not all(field in cleaned for field in day_fields):
                return

            if cleaned[closed_key]:
                slots.append(TimeSlot.create(name=day, opens=None, closes=None))
                continue

            slots.append(
                TimeSlot.create(
                    name=day,
                    opens=cleaned[opens_key],
                    closes=cleaned[closes_key],
                ),
            )

        cleaned['opening_hours'] = OpeningHours(tuple(slots))

    def _clean_delivery_terms(self, cleaned):

        delivery_fields = (
            'pickup',
            'home_delivery',
            'delivery_radius',
            'delivery_currency',
            'delivery_base_cost',
        )

        if not all(field in cleaned for field in delivery_fields):
            return

        base_cost = None
        if cleaned['home_delivery'] and cleaned['delivery_base_cost'] is not None:
            base_cost = Money.create(
                cleaned['delivery_currency'],
                cleaned['delivery_base_cost'],
            )

        cleaned['delivery_terms'] = DeliveryTerms.create(
            pickup=cleaned['pickup'],
            home_delivery=cleaned['home_delivery'],
            radius=cleaned['delivery_radius'],
            base_cost=base_cost,
        )

    @classmethod
    def _service_initial(cls, profile):
        delivery = profile.delivery_terms
        initial = {
            'pickup': delivery.pickup if delivery else False,
            'home_delivery': delivery.home_delivery if delivery else False,
            'delivery_radius': (
                delivery.radius.value if delivery and delivery.radius else None
            ),
            'delivery_currency': (
                delivery.base_cost.currency
                if delivery and delivery.base_cost
                else Money.ARS().currency
            ),
            'delivery_base_cost': (
                delivery.base_cost.amount if delivery and delivery.base_cost else None
            ),
            'preparation_tags': sorted(tag.value for tag in profile.preparation_tags),
        }
        for day, default_closed in cls.day_defaults:
            initial.update(cls._day_initial(profile.opening_hours, day, default_closed))
        return initial

    @staticmethod
    def _day_initial(opening_hours, day, default_closed):
        slot = None
        if opening_hours is not None:
            slot = next(item for item in opening_hours.slots if item.name == day)

        if slot is None or slot.closed:
            return {
                f'{day}_closed': default_closed if slot is None else True,
                f'{day}_opens': None,
                f'{day}_closes': None,
            }

        return {
            f'{day}_closed': False,
            f'{day}_opens': slot.opens,
            f'{day}_closes': slot.closes,
        }


class PharmacyProfileForm(PharmacyDetailsForm, PharmacyServiceForm):
    def clean(self):
        cleaned = super().clean()
        self._clean_location(cleaned)
        self._clean_opening_hours(cleaned)
        self._clean_delivery_terms(cleaned)
        return cleaned

    @property
    def cleaned_params(self):
        data = self.cleaned_data
        return UpdatePharmacyProfileParams(
            visible=data['visible'],
            kind=data['kind'],
            trade_name=data['trade_name'],
            legal_name=data['legal_name'],
            cuit=data['cuit'],
            technical_director=data['technical_director'],
            license=data['license'],
            request_email=data['request_email'],
            phone=data['phone'],
            website=data['website'],
            location=data['location'],
            opening_hours=data['opening_hours'],
            delivery_terms=data['delivery_terms'],
            preparation_tags=data['preparation_tags'],
        )

    @classmethod
    def initial_from(cls, profile: PharmacyAccountProfile):
        initial = cls._details_initial(profile)
        initial.update(cls._service_initial(profile))
        return initial
