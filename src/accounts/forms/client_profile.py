from django import forms

from accounts.commands.update_client_profile import UpdateClientProfileParams
from accounts.models import MailPreferences, SearchRadius
from accounts.queries.client_profile import ClientAccountProfile
from shared.forms import TypedForm
from shared.values import (
    Coordinates,
    IncompleteLocationError,
    InvalidCoordinatesError,
    Location,
    PhoneNumber,
    UnselectedSearchPlaceError,
)


class ClientProfileForm(TypedForm[UpdateClientProfileParams]):
    first_name = forms.CharField(label='Nombre', max_length=150)

    last_name = forms.CharField(label='Apellido', max_length=150)

    phone = forms.CharField(label='Teléfono', max_length=30, required=False)

    health_insurance_number = forms.CharField(
        label='N.º de Beneficiario (Obra Social / Prepaga)',
        max_length=40,
        required=False,
    )

    address = forms.CharField(label='Dirección', max_length=200, required=False)

    locality = forms.CharField(label='Localidad', max_length=120, required=False)

    postal_code = forms.CharField(
        label='Código postal',
        max_length=Location.postal_code_max_length,
        required=False,
    )

    latitude = forms.FloatField(widget=forms.HiddenInput, required=False)

    longitude = forms.FloatField(widget=forms.HiddenInput, required=False)

    search_radius = forms.TypedChoiceField(
        label='Radio de búsqueda de farmacias por defecto',
        coerce=int,
        required=False,
        choices=[
            ('', ''),
            *[(radius.value, f'Hasta {radius.value} km') for radius in SearchRadius],
        ],
        widget=forms.Select(attrs={'x-ref': 'radius'}),
    )

    mail_on_reply = forms.BooleanField(
        label='Cuando una farmacia responde o envía un presupuesto',
        required=False,
        help_text='Un mail por conversación, como máximo cada 15 minutos.',
    )

    mail_on_status_change = forms.BooleanField(
        label='Cuando cambia el estado de mi pedido',
        required=False,
        help_text='En preparación, listo para retirar, entregado.',
    )

    mail_on_quote_expiry = forms.BooleanField(
        label='Recordatorio si un presupuesto está por vencer',
        required=False,
    )

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip()

    def clean_last_name(self):
        return self.cleaned_data['last_name'].strip()

    def clean_phone(self):
        number = self.cleaned_data['phone'].strip()
        if not number:
            return None
        return PhoneNumber.AR(number)

    def clean_search_radius(self):
        radius = self.cleaned_data['search_radius']
        if not radius:
            return None
        return SearchRadius(radius)

    def clean_health_insurance_number(self):
        return self.cleaned_data['health_insurance_number'].strip()

    def clean(self):
        cleaned = super().clean()
        self._clean_location(cleaned)
        self._clean_mail_preferences(cleaned)
        return cleaned

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

    def _clean_mail_preferences(self, cleaned):
        mail_fields = ('mail_on_reply', 'mail_on_status_change', 'mail_on_quote_expiry')
        if not all(field in cleaned for field in mail_fields):
            return

        cleaned['mail_preferences'] = MailPreferences(
            on_reply=cleaned['mail_on_reply'],
            on_status_change=cleaned['mail_on_status_change'],
            on_quote_expiry=cleaned['mail_on_quote_expiry'],
        )

    @property
    def cleaned_params(self):
        data = self.cleaned_data
        return UpdateClientProfileParams(
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone=data['phone'],
            location=data['location'],
            search_radius=data['search_radius'],
            health_insurance_number=data['health_insurance_number'],
            mail_preferences=data['mail_preferences'],
        )

    @classmethod
    def initial_from(cls, profile: ClientAccountProfile):
        phone = profile.phone
        location = profile.location
        mail = profile.mail_preferences
        return {
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'phone': phone.number if phone else '',
            'health_insurance_number': profile.health_insurance_number,
            'address': location.address if location else '',
            'locality': location.locality if location else '',
            'postal_code': location.postal_code if location else '',
            'latitude': (
                location.coordinates.latitude
                if location and location.coordinates
                else None
            ),
            'longitude': (
                location.coordinates.longitude
                if location and location.coordinates
                else None
            ),
            'search_radius': profile.search_radius or '',
            'mail_on_reply': mail.on_reply if mail else True,
            'mail_on_status_change': mail.on_status_change if mail else True,
            'mail_on_quote_expiry': mail.on_quote_expiry if mail else True,
        }
