from django import forms
from django.core.validators import DecimalValidator

from accounts.commands.update_pharmacy_profile import UpdatePharmacyProfileParams
from accounts.exceptions import (
    DeliveryCostWithoutHomeDeliveryError,
    InvalidDeliveryTermsError,
)
from accounts.models import (
    Cuit,
    DeliveryTerms,
    OpeningHours,
    PharmacyKind,
    PreparationTag,
)
from accounts.queries.pharmacy_profile import PharmacyAccountProfile
from shared.forms import TypedForm
from shared.values import (
    Coordinates,
    IncompleteLocationError,
    InvalidCoordinatesError,
    InvalidTimeSlotError,
    Location,
    Money,
    PhoneNumber,
    TimeSlot,
    UnselectedSearchPlaceError,
)


class PharmacyDetailsForm(TypedForm):
    first_name = forms.CharField(label='Nombre', max_length=150)

    last_name = forms.CharField(label='Apellido', max_length=150)

    kind = forms.ChoiceField(
        label='Tipo',
        required=False,
        choices=PharmacyKind.choices,
        widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'}),
    )

    trade_name = forms.CharField(
        label='Nombre comercial',
        max_length=150,
        required=False,
    )

    legal_name = forms.CharField(label='Razón social', max_length=150, required=False)

    cuit = forms.CharField(label='CUIT', max_length=13, required=False)

    technical_director = forms.CharField(
        label='Director técnico',
        max_length=150,
        required=False,
    )

    license = forms.CharField(label='Matrícula', max_length=40, required=False)

    request_email = forms.EmailField(
        label='Email para solicitudes',
        required=False,
        help_text='Acá llega cada solicitud nueva y cada mensaje de un cliente.',
    )

    phone = forms.CharField(label='Teléfono', max_length=30, required=False)

    website = forms.URLField(label='Sitio web', required=False, assume_scheme='https')

    address = forms.CharField(label='Dirección', max_length=200, required=False)

    locality = forms.CharField(label='Localidad', max_length=120, required=False)

    postal_code = forms.CharField(
        label='Código postal',
        max_length=Location.postal_code_max_length,
        required=False,
    )

    latitude = forms.FloatField(widget=forms.HiddenInput, required=False)

    longitude = forms.FloatField(widget=forms.HiddenInput, required=False)

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip()

    def clean_last_name(self):
        return self.cleaned_data['last_name'].strip()

    def clean_trade_name(self):
        return self.cleaned_data['trade_name'].strip()

    def clean_legal_name(self):
        return self.cleaned_data['legal_name'].strip()

    def clean_cuit(self):
        number = self.cleaned_data['cuit'].strip()
        if not number:
            return None
        return Cuit.create(number)

    def clean_technical_director(self):
        return self.cleaned_data['technical_director'].strip()

    def clean_license(self):
        return self.cleaned_data['license'].strip()

    def clean_phone(self):
        number = self.cleaned_data['phone'].strip()
        if not number:
            return None
        return PhoneNumber.AR(number)

    def clean_website(self):
        return (self.cleaned_data.get('website') or '').strip()

    def _clean_location(self, cleaned):
        address = cleaned.get('address', '')
        locality = cleaned.get('locality', '')
        postal_code = cleaned.get('postal_code', '')

        if not any(value.strip() for value in (address, locality, postal_code)):
            cleaned['location'] = None
            return

        try:
            coordinates = Coordinates.create(
                cleaned.get('latitude'),
                cleaned.get('longitude'),
            )
        except InvalidCoordinatesError:
            self.add_error('address', UnselectedSearchPlaceError())
            return

        try:
            cleaned['location'] = Location.create(
                address,
                locality,
                postal_code,
                coordinates,
            )
        except IncompleteLocationError as error:
            self.add_error('postal_code', error)

    @classmethod
    def _details_initial(cls, profile):
        return {
            'first_name': profile.first_name,
            'last_name': profile.last_name,
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
            'latitude': (
                profile.location.coordinates.latitude
                if profile.location and profile.location.coordinates
                else None
            ),
            'longitude': (
                profile.location.coordinates.longitude
                if profile.location and profile.location.coordinates
                else None
            ),
        }


class PharmacyServiceForm(TypedForm):
    day_labels = (
        (OpeningHours.weekday, 'Lun a vie'),
        (OpeningHours.saturday, 'Sábados'),
        (OpeningHours.sunday, 'Dom y feriados'),
    )

    pickup = forms.BooleanField(label='Retiro en el local', required=False)

    home_delivery = forms.BooleanField(label='Envío a domicilio', required=False)

    delivery_currency = forms.ChoiceField(
        label='Moneda',
        required=False,
        choices=[(currency, currency.value) for currency in Money.Currency],
        initial=Money.ARS().currency,
    )

    delivery_base_cost = forms.DecimalField(
        label='Costo base de envío',
        required=False,
        localize=True,
    )

    preparation_tags = forms.MultipleChoiceField(
        label='Preparaciones que realizás',
        choices=PreparationTag.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'checkbox checkbox-primary'},
        ),
        help_text='Se usan para los filtros del mapa.',
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self._configure_delivery_cost()

        for day, label in self.day_labels:
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

    def _clean_opening_hours(self, cleaned):
        slots = []
        for day in OpeningHours.days:
            opens_key = f'{day}_opens'
            closes_key = f'{day}_closes'

            try:
                slots.append(
                    TimeSlot.create(
                        name=day,
                        opens=cleaned.get(opens_key),
                        closes=cleaned.get(closes_key),
                    ),
                )
            except InvalidTimeSlotError as error:
                field = closes_key if cleaned[opens_key] is not None else opens_key
                self.add_error(field, error)
                return

        cleaned['opening_hours'] = OpeningHours.create(slots)

    def _clean_delivery_terms(self, cleaned):
        base_cost = None
        if cleaned.get('delivery_base_cost') is not None:
            base_cost = Money.create(
                cleaned['delivery_currency'],
                cleaned['delivery_base_cost'],
            )

        try:
            cleaned['delivery_terms'] = DeliveryTerms.create(
                pickup=cleaned.get('pickup'),
                home_delivery=cleaned.get('home_delivery'),
                base_cost=base_cost,
            )
        except DeliveryCostWithoutHomeDeliveryError as error:
            self.add_error('delivery_base_cost', error)
        except InvalidDeliveryTermsError as error:
            self.add_error('home_delivery', error)

    @classmethod
    def _service_initial(cls, profile):
        delivery = profile.delivery_terms

        initial = {
            'pickup': delivery.pickup if delivery else False,
            'home_delivery': delivery.home_delivery if delivery else False,
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

        hours = profile.opening_hours or OpeningHours(
            [
                TimeSlot.create(name=day, opens=None, closes=None)
                for day in OpeningHours.days
            ]
        )

        for slot in hours.slots:
            initial[f'{slot.name}_opens'] = slot.opens
            initial[f'{slot.name}_closes'] = slot.closes

        return initial


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
            first_name=data['first_name'],
            last_name=data['last_name'],
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
