from contextlib import suppress

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from orders.models import DeliveryPreference, PreparationType, Urgency
from shared.values import (
    Coordinates,
    IncompleteLocationError,
    InvalidCoordinatesError,
    Location,
)

PRESCRIPTION_EXTENSIONS = ('pdf', 'jpg', 'jpeg', 'png')
PRESCRIPTION_MAX_SIZE = 10 * 1024 * 1024


class NewOrderForm(forms.Form):
    preparation_type = forms.ChoiceField(
        label='Tipo de preparación',
        choices=PreparationType.choices,
    )

    presentation = forms.CharField(
        label='Cantidad o presentación',
        max_length=60,
        widget=forms.TextInput(attrs={'placeholder': 'Por ejemplo: 60 ml'}),
    )

    formula = forms.CharField(
        label='¿Qué preparación necesitás?',
        max_length=2000,
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text=(
            'Escribila como figura en la receta. Si tenés dudas, adjuntá la receta: '
            'la farmacia la interpreta.'
        ),
    )

    prescription_file = forms.FileField(
        label='Receta médica',
        required=False,
        validators=[FileExtensionValidator(PRESCRIPTION_EXTENSIONS)],
        widget=forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'}),
        help_text='Si no la tenés a mano, podés enviarla después desde el chat.',
    )

    urgency = forms.ChoiceField(
        label='¿Para cuándo la necesitás?',
        choices=Urgency.choices,
        widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'}),
    )

    delivery_preferences = forms.MultipleChoiceField(
        label='¿Cómo preferís recibirla?',
        choices=DeliveryPreference.choices,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'checkbox checkbox-primary'},
        ),
    )

    search_area = forms.CharField(label='¿Dónde buscamos farmacias?', max_length=200)

    latitude = forms.FloatField(widget=forms.HiddenInput, required=False)

    longitude = forms.FloatField(widget=forms.HiddenInput, required=False)

    address = forms.CharField(widget=forms.HiddenInput, required=False)

    locality = forms.CharField(widget=forms.HiddenInput, required=False)

    postal_code = forms.CharField(widget=forms.HiddenInput, required=False)

    save_location = forms.BooleanField(
        label='Guardar esta dirección en mi perfil',
        required=False,
        initial=True,
    )

    note = forms.CharField(
        label='Notas para la farmacia',
        max_length=1000,
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'placeholder': (
                    'Por ejemplo: soy alérgica al alcohol, prefiero frasco gotero…'
                ),
            },
        ),
    )

    def clean_prescription_file(self):
        file = self.cleaned_data['prescription_file']
        if file and file.size > PRESCRIPTION_MAX_SIZE:
            message = 'La receta puede pesar hasta 10 MB.'
            raise ValidationError(message, code='too_large')
        return file

    def clean(self):
        cleaned = super().clean()
        if 'search_area' not in cleaned:
            return cleaned
        try:
            cleaned['search_coordinates'] = Coordinates.create(
                cleaned.get('latitude'),
                cleaned.get('longitude'),
            )
        except InvalidCoordinatesError:
            self.add_error(
                'search_area',
                'Elegí una opción de la lista o usá tu ubicación.',
            )
            return cleaned
        if cleaned.get('save_location'):
            with suppress(IncompleteLocationError):
                cleaned['profile_location'] = Location.create(
                    cleaned.get('address'),
                    cleaned.get('locality'),
                    cleaned.get('postal_code'),
                    cleaned['search_coordinates'],
                )
        return cleaned

    @classmethod
    def initial_from(cls, location: Location | None):
        if not location or not location.coordinates:
            return {}
        return {
            'search_area': f'{location.address}, {location.locality}',
            'latitude': location.coordinates.latitude,
            'longitude': location.coordinates.longitude,
            'address': location.address,
            'locality': location.locality,
            'postal_code': location.postal_code,
        }
