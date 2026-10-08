from django import forms

from accounts.commands.update_client_profile import UpdateClientProfileParams
from accounts.models import MailPreferences, SearchRadius
from accounts.queries.client_profile import ClientAccountProfile
from shared.forms import TypedForm
from shared.values import Location, PhoneNumber


class ClientProfileForm(TypedForm[UpdateClientProfileParams]):
    first_name = forms.CharField(label='Nombre', max_length=150)

    last_name = forms.CharField(label='Apellido', max_length=150)

    phone = forms.CharField(label='Teléfono', max_length=30)

    health_insurance_number = forms.CharField(
        label='N.º de Beneficiario (Obra Social / Prepaga)',
        max_length=40,
        required=False,
    )

    address = forms.CharField(label='Dirección', max_length=200)

    locality = forms.CharField(label='Barrio / localidad', max_length=120)

    postal_code = forms.CharField(
        label='Código postal',
        max_length=Location.postal_code_max_length,
    )

    search_radius = forms.TypedChoiceField(
        label='Radio de búsqueda',
        coerce=int,
        choices=[(radius.value, f'Hasta {radius.value} km') for radius in SearchRadius],
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
        return PhoneNumber.AR(self.cleaned_data['phone'])

    def clean_search_radius(self):
        return SearchRadius(self.cleaned_data['search_radius'])

    def clean_health_insurance_number(self):
        return self.cleaned_data['health_insurance_number'].strip()

    def clean(self):
        cleaned = super().clean()
        self._clean_location(cleaned)
        self._clean_mail_preferences(cleaned)
        return cleaned

    def _clean_location(self, cleaned):
        location_fields = ('address', 'locality', 'postal_code')
        if not all(field in cleaned for field in location_fields):
            return

        cleaned['location'] = Location.create(
            cleaned['address'],
            cleaned['locality'],
            cleaned['postal_code'],
        )

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
            'search_radius': int(profile.search_radius or SearchRadius.KM5),
            'mail_on_reply': mail.on_reply if mail else True,
            'mail_on_status_change': mail.on_status_change if mail else True,
            'mail_on_quote_expiry': mail.on_quote_expiry if mail else True,
        }
