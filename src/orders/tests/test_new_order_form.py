import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from orders.forms import PRESCRIPTION_MAX_SIZE, NewOrderForm
from shared.values import Coordinates, Location

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

ADDRESS = {
    'save_location': 'on',
    'address': 'Avenida Santa Fe 3820',
    'locality': 'Palermo',
    'postal_code': 'C1425BHN',
}


def test_order_without_prescription_is_valid():
    form = NewOrderForm(data=ORDER)

    assert form.is_valid()
    assert form.cleaned_data['prescription_file'] is None
    assert form.cleaned_data['search_coordinates'] == Coordinates(
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


def test_order_keeps_a_complete_address_for_the_profile():
    form = NewOrderForm(data={**ORDER, **ADDRESS})

    assert form.is_valid()
    assert form.cleaned_data['profile_location'] == Location.create(
        'Avenida Santa Fe 3820',
        'Palermo',
        'C1425BHN',
        Coordinates(-34.5842582, -58.4174826),
    )


def test_order_skips_an_incomplete_address_for_the_profile():
    form = NewOrderForm(data={**ORDER, **ADDRESS, 'postal_code': ''})

    assert form.is_valid()
    assert 'profile_location' not in form.cleaned_data
