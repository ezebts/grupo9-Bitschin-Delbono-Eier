import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict

from orders.forms import NewOrderForm, PrescriptionFilesField
from shared.values import Coordinates

ORDER = {
    'preparation_type': 'solution',
    'presentation': '60 ml',
    'formula': 'Minoxidil 5% en solución capilar',
    'urgency': 'this_week',
    'delivery_preferences': ['pickup'],
    'search_area': 'Avenida Santa Fe 3820, Palermo',
    'latitude': '-34.5842582',
    'longitude': '-58.4174826',
}


def _form(data=None, files=()):
    return NewOrderForm(
        data=data or ORDER,
        files=MultiValueDict({'prescription_files': list(files)}),
    )


def test_order_without_prescription_is_valid():
    form = _form()

    assert form.is_valid()
    assert form.cleaned_data['prescription_files'] == []
    assert form.cleaned_data['search_coordinates'] == Coordinates(
        -34.5842582,
        -58.4174826,
    )


def test_order_needs_a_place_from_the_list():
    form = _form({**ORDER, 'latitude': '', 'longitude': ''})

    assert not form.is_valid()
    assert form.errors['search_area'] == [
        'Elegí una opción de la lista o usá tu ubicación.',
    ]


def test_order_keeps_every_prescription():
    files = [
        SimpleUploadedFile('receta.pdf', b'%PDF-1.7'),
        SimpleUploadedFile('foto.jpg', b'jpg'),
    ]

    form = _form(files=files)

    assert form.is_valid()
    assert [file.name for file in form.cleaned_data['prescription_files']] == [
        'receta.pdf',
        'foto.jpg',
    ]


@pytest.mark.parametrize(
    ('name', 'size'),
    [
        ('receta.txt', 10),
        ('receta.pdf', PrescriptionFilesField.max_size + 1),
    ],
)
def test_order_rejects_an_invalid_prescription(name, size):
    form = _form(files=[SimpleUploadedFile(name, b'0' * size)])

    assert not form.is_valid()
    assert 'prescription_files' in form.errors
