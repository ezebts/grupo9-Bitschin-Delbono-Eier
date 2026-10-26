from dataclasses import dataclass

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator

from accounts.models import PreparationTag
from orders.models import DeliveryPreference, Urgency
from shared.forms import TypedForm
from shared.values import (
    Coordinates,
    InvalidCoordinatesError,
    Location,
    UnselectedSearchPlaceError,
)

PRESCRIPTION_EXTENSIONS = ('pdf', 'jpg', 'jpeg', 'png')
PRESCRIPTION_MAX_SIZE = 10 * 1024 * 1024


@dataclass(frozen=True)
class NewOrderParams:
    preparation_tag: PreparationTag
    presentation: str
    formula: str
    prescription_file: UploadedFile | None
    urgency: str
    delivery_preferences: tuple[str, ...]
    search_area: str
    search_coordinates: Coordinates
    note: str


class OrderPrescriptionForm(forms.Form):
    prescription_file = forms.FileField(
        label='Receta médica',
        validators=[
            FileExtensionValidator(
                PRESCRIPTION_EXTENSIONS,
                message='La receta tiene que ser un PDF, JPG o PNG.',
            ),
        ],
        error_messages={'required': 'Elegí un archivo de receta.'},
        widget=forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'}),
    )

    def clean_prescription_file(self):
        file = self.cleaned_data['prescription_file']
        if file and file.size > PRESCRIPTION_MAX_SIZE:
            message = 'La receta puede pesar hasta 10 MB.'
            raise ValidationError(message, code='too_large')
        return file


class NewOrderForm(TypedForm[NewOrderParams]):
    preparation_tag = forms.ChoiceField(
        label='Tipo de preparación',
        choices=PreparationTag.choices,
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
            self.add_error('search_area', UnselectedSearchPlaceError())
        return cleaned

    @property
    def cleaned_params(self) -> NewOrderParams:
        data = self.cleaned_data
        return NewOrderParams(
            preparation_tag=PreparationTag(data['preparation_tag']),
            presentation=data['presentation'],
            formula=data['formula'],
            prescription_file=data['prescription_file'],
            urgency=data['urgency'],
            delivery_preferences=tuple(data['delivery_preferences']),
            search_area=data['search_area'],
            search_coordinates=data['search_coordinates'],
            note=data['note'],
        )

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
