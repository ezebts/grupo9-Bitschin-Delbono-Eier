import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from orders.forms import PRESCRIPTION_MAX_SIZE, NewOrderForm
from shared.values import Coordinates

ORDER = {
    'preparation_tag': 'solutions',
    'presentation': '60 ml',
    'formula': 'Minoxidil 5% en solución capilar',
    'urgency': 'this_week',
    'delivery_preferences': ['pickup'],
    'search_area': 'Avenida Santa Fe 3820, Palermo',
    'latitude': '-34.5842582',
    'longitude': '-58.4174826',
}


def test_order_without_prescription_is_valid():
    form = NewOrderForm(data=ORDER)

    assert form.is_valid()
    assert form.cleaned_params.prescription_file is None
    assert form.cleaned_params.search_coordinates == Coordinates(
        -34.5842582,
        -58.4174826,
    )


def test_order_needs_a_place_from_the_list():
    form = NewOrderForm(data={**ORDER, 'latitude': '', 'longitude': ''})

    assert not form.is_valid()
    assert form.errors['search_area'] == [
        'Elegí una opción de la lista o usá tu ubicación.',
    ]


@pytest.mark.parametrize(
    ('name', 'size'),
    [
        ('receta.txt', 10),
        ('receta.pdf', PRESCRIPTION_MAX_SIZE + 1),
    ],
)
def test_order_rejects_an_invalid_prescription(name, size):
    prescription = SimpleUploadedFile(name, b'0' * size)

    form = NewOrderForm(data=ORDER, files={'prescription_file': prescription})

    assert not form.is_valid()
    assert 'prescription_file' in form.errors
