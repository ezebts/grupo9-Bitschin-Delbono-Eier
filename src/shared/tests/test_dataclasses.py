from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from enum import StrEnum

from shared.dataclasses import asdict, from_dict
from shared.values import Coordinates, Location, Money, TimeSlot


class Day(StrEnum):
    WEEKDAY = 'weekday'


@dataclass(frozen=True)
class Schedule:
    day: Day
    opens: time | None
    cost: Decimal


def test_asdict_serializes_enums_times_and_decimals():
    schedule = Schedule(Day.WEEKDAY, time(9, 0), Decimal('1500.50'))

    assert asdict(schedule) == {
        'day': 'weekday',
        'opens': '09:00',
        'cost': '1500.50',
    }


def test_from_dict_rebuilds_enums_times_and_decimals():
    raw = {
        'day': 'weekday',
        'opens': '09:00',
        'cost': '1500.50',
    }

    assert from_dict(Schedule, raw) == Schedule(
        Day.WEEKDAY,
        time(9, 0),
        Decimal('1500.50'),
    )


def test_from_dict_returns_none_when_the_payload_is_empty_or_invalid():
    assert from_dict(Schedule, {}) is None
    assert from_dict(Schedule, None) is None
    assert from_dict(Schedule, {'day': 'weekday'}) is None


def test_nested_value_objects_round_trip():
    location = Location.create(
        'Av. Santa Fe 3820',
        'Palermo',
        '1425',
        Coordinates.create(-34.58, -58.42),
    )
    money = Money.ARS('1500.50')
    closed = TimeSlot.create(name='sunday', opens=None, closes=None)

    assert from_dict(Location, asdict(location)) == location
    assert from_dict(Money, asdict(money)) == money
    assert from_dict(TimeSlot, asdict(closed)) == closed


def test_a_saved_location_without_coordinates_stays_without_them():
    raw = {
        'address': 'Av. Santa Fe 3820',
        'locality': 'Palermo',
        'postal_code': '1425',
    }

    assert from_dict(Location, raw).coordinates is None
