from datetime import time
from decimal import Decimal

import pytest

from shared.values import (
    Coordinates,
    IncompleteLocationError,
    InvalidCoordinatesError,
    InvalidMoneyError,
    InvalidPhoneNumberError,
    InvalidTimeSlotError,
    Location,
    Money,
    PhoneNumber,
    TimeSlot,
)


def test_argentine_phone_keeps_only_digits():
    phone = PhoneNumber.AR('11 5555-4444')

    assert phone.number == '1155554444'


def test_argentine_phone_rejects_a_short_number():
    with pytest.raises(InvalidPhoneNumberError):
        PhoneNumber.AR('11 5555')


def test_coordinates_accept_a_point_in_range():
    point = Coordinates.create('-34.58', -58.42)

    assert point == Coordinates(-34.58, -58.42)


def test_coordinates_reject_a_latitude_out_of_range():
    with pytest.raises(InvalidCoordinatesError):
        Coordinates.create(91, 0)


def test_coordinates_reject_a_boolean():
    latitude = True

    with pytest.raises(InvalidCoordinatesError):
        Coordinates.create(latitude, 0)


def test_location_accepts_a_classic_postal_code():
    location = Location.create('  Av. Santa Fe 3820 ', ' Palermo ', '1425')

    assert location.address == 'Av. Santa Fe 3820'
    assert location.locality == 'Palermo'
    assert location.postal_code == '1425'
    assert location.coordinates is None


def test_location_stores_a_cpa_in_uppercase():
    location = Location.create('Av. Santa Fe 3820', 'Palermo', 'c1425bgh')

    assert location.postal_code == 'C1425BGH'


def test_location_rejects_an_invalid_postal_code():
    with pytest.raises(IncompleteLocationError):
        Location.create('Av. Santa Fe 3820', 'Palermo', '142')


def test_location_rejects_a_blank_address():
    with pytest.raises(IncompleteLocationError):
        Location.create('  ', 'Palermo', '1425')


def test_location_keeps_coordinates():
    point = Coordinates.create(-34.58, -58.42)

    location = Location.create('Av. Santa Fe 3820', 'Palermo', '1425', point)

    assert location.coordinates == point


def test_location_rejects_coordinates_that_are_not_a_point():
    with pytest.raises(InvalidCoordinatesError):
        Location.create('Av. Santa Fe 3820', 'Palermo', '1425', (-34.58, -58.42))


def test_time_slot_is_open_between_its_hours():
    slot = TimeSlot.create(name='weekday', opens=time(9, 0), closes=time(21, 0))

    assert slot.closed is False


def test_time_slot_without_hours_is_closed():
    slot = TimeSlot.create(name='sunday', opens=None, closes=None)

    assert slot.closed is True


def test_time_slot_rejects_a_close_that_is_not_after_open():
    with pytest.raises(InvalidTimeSlotError):
        TimeSlot.create(name='weekday', opens=time(21, 0), closes=time(9, 0))


def test_time_slot_rejects_a_single_hour():
    with pytest.raises(InvalidTimeSlotError):
        TimeSlot.create(name='weekday', opens=time(9, 0), closes=None)


def test_pesos_are_quantized_to_centavos():
    money = Money.ARS('1500.505')

    assert money.amount == Decimal('1500.50')
    assert money.currency is Money.Currency.ARS


def test_create_uses_the_currency_constructor():
    assert Money.create('USD', '10') == Money.USD('10')


def test_money_rejects_a_negative_amount():
    with pytest.raises(InvalidMoneyError):
        Money.ARS('-0.01')
