from datetime import time
from zoneinfo import ZoneInfo

import pytest

from accounts.models import (
    DeliveryTerms,
    OpeningHours,
    Pharmacy,
    PharmacyKind,
    PreparationTag,
    SearchRadius,
)
from accounts.queries.find_nearby_pharmacies import find_nearby_pharmacies
from shared.values import Coordinates, Location, Money, TimeSlot

pytestmark = pytest.mark.django_db

ARGENTINA = ZoneInfo('America/Argentina/Buenos_Aires')

ORIGIN = Coordinates.create(-34.584, -58.417)
NEAR = Coordinates.create(-34.588, -58.417)
FAR = Coordinates.create(-34.70, -58.42)


def _pharmacy(email, *, point, kind, delivery=False, tags=()):
    pharmacy = Pharmacy.objects.create(
        trade_name=email.split('@')[0],
        kind=kind,
        visible=True,
    )
    pharmacy.update_location(
        Location.create('Calle 100', 'Palermo', '1425', point),
    )
    if delivery:
        pharmacy.update_delivery_terms(
            DeliveryTerms.create(
                pickup=True,
                home_delivery=True,
                base_cost=Money.create('ARS', '2500'),
            ),
        )
    if tags:
        pharmacy.update_preparation_tags(set(tags))
    pharmacy.save()
    return pharmacy


def test_nearby_pharmacies_keep_only_places_inside_the_radius():
    near = _pharmacy(
        'cerca@example.com',
        point=NEAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
    )
    _pharmacy(
        'lejos@example.com',
        point=FAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
    )

    found = find_nearby_pharmacies(
        ORIGIN,
        radius_km=SearchRadius.create(3),
        include_pharmacies=True,
        include_labs=True,
        open_now=False,
        home_delivery=False,
        timezone=ARGENTINA,
    )

    assert [pharmacy.id for pharmacy in found] == [near.pk]


def test_nearby_pharmacies_can_keep_labs_that_deliver_the_preparation():
    lab = _pharmacy(
        'lab@example.com',
        point=NEAR,
        kind=PharmacyKind.PREPARATION_LAB,
        delivery=True,
        tags={PreparationTag.SOLUTIONS},
    )
    _pharmacy(
        'farmacia@example.com',
        point=NEAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
        delivery=True,
    )

    found = find_nearby_pharmacies(
        ORIGIN,
        radius_km=SearchRadius.create(3),
        include_pharmacies=False,
        include_labs=True,
        open_now=False,
        home_delivery=True,
        timezone=ARGENTINA,
        preparation_tag=PreparationTag.SOLUTIONS,
    )

    assert [pharmacy.id for pharmacy in found] == [lab.pk]
    assert found[0].is_laboratory


def _hours(*slots):
    return OpeningHours(slots)


def test_open_now_keeps_only_pharmacies_open_today():
    open_pharmacy = _pharmacy(
        'abierta@example.com',
        point=NEAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
    )
    open_pharmacy.update_opening_hours(
        _hours(
            *(
                TimeSlot.create(name=day, opens=time(0, 0), closes=time(23, 59))
                for day in OpeningHours.days
            ),
        ),
    )
    open_pharmacy.save()
    closed = _pharmacy(
        'cerrada@example.com',
        point=NEAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
    )
    closed.update_opening_hours(
        _hours(
            *(
                TimeSlot.create(name=day, opens=None, closes=None)
                for day in OpeningHours.days
            ),
        ),
    )
    closed.save()

    found = find_nearby_pharmacies(
        ORIGIN,
        radius_km=SearchRadius.create(3),
        include_pharmacies=True,
        include_labs=False,
        open_now=True,
        home_delivery=False,
        timezone=ARGENTINA,
    )

    assert [pharmacy.id for pharmacy in found] == [open_pharmacy.pk]


def test_opening_hours_are_not_required_to_build_the_list():
    pharmacy = _pharmacy(
        'sin-horario@example.com',
        point=NEAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
    )
    pharmacy.update_opening_hours(
        OpeningHours(
            slots=(
                TimeSlot.create('weekday', opens=None, closes=None),
                TimeSlot.create('saturday', opens=None, closes=None),
                TimeSlot.create('sunday', opens=None, closes=None),
            ),
        ),
    )
    pharmacy.save()

    found = find_nearby_pharmacies(
        ORIGIN,
        radius_km=SearchRadius.create(3),
        include_pharmacies=True,
        include_labs=False,
        open_now=False,
        home_delivery=False,
        timezone=ARGENTINA,
    )

    assert found[0].hours == 'Cerrado'
