from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from orders.models import DeliveryPreference, PreparationType, Urgency
from shared.values import Coordinates, InvalidCoordinatesError


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class PrescriptionFilesField(forms.FileField):
    too_large_message = 'Cada archivo puede pesar hasta 10 MB.'
    extensions = ('pdf', 'jpg', 'jpeg', 'png')
    max_size = 10 * 1024 * 1024

    def __init__(self, **kwargs):
        accept = ','.join(f'.{extension}' for extension in self.extensions)
        super().__init__(
            widget=MultipleFileInput(attrs={'accept': accept}),
            validators=[FileExtensionValidator(self.extensions)],
            **kwargs,
        )

    def clean(self, data, initial=None):
        files = data if isinstance(data, list | tuple) else [data]
        cleaned = []
        for file in files or [None]:
            cleaned_file = super().clean(file, initial)
            if cleaned_file and cleaned_file.size > self.max_size:
                raise ValidationError(self.too_large_message, code='too_large')
            cleaned.append(cleaned_file)
        return [file for file in cleaned if file]


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

    prescription_files = PrescriptionFilesField(
        label='Receta médica',
        required=False,
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
