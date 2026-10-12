import re
from dataclasses import dataclass
from typing import Self

from django.contrib.gis.db.models import PointField
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import models
from django.db.models import CharField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast

from accounts.exceptions import (
    DeliveryCostWithoutHomeDeliveryError,
    InvalidCuitError,
    InvalidDeliveryTermsError,
    PharmacyCantBecomeVisible,
    PharmacyCantClearSearchData,
)
from accounts.models.base import User
from shared.dataclasses import asdict, from_dict
from shared.values import Coordinates, Location, Money, PhoneNumber, TimeSlot

GEO_WGS84_LAT_LONG = 4326


class PharmacyKind(models.TextChoices):
    PHARMACY_WITH_LAB = 'pharmacy_with_lab', 'Farmacia con laboratorio magistral'
    PREPARATION_LAB = 'preparation_lab', 'Laboratorio de preparaciones'


class PreparationTag(models.TextChoices):
    CAPSULES = 'capsules', 'Cápsulas'
    CREAMS = 'creams', 'Cremas y geles'
    SOLUTIONS = 'solutions', 'Soluciones y lociones'
    SYRUPS = 'syrups', 'Jarabes'
    OVULES = 'ovules', 'Óvulos y supositorios'
    HORMONAL = 'hormonal', 'Hormonales'
    DERMATOLOGY = 'dermatology', 'Dermatología'
    VETERINARY = 'veterinary', 'Veterinaria'
    GLUTEN_FREE = 'gluten_free', 'Sin TACC'


@dataclass(frozen=True)
class Cuit:
    number: str
    length = 11
    modulus = 11
    replaced_check = 9
    weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    prefixes = ('20', '23', '24', '27', '30', '33', '34')

    @classmethod
    def create(cls, raw):
        number = re.sub(r'\D', '', raw or '')

        if (
            len(number) != cls.length
            or number[:2] not in cls.prefixes
            or not cls._check_digit_matches(number)
        ):
            raise InvalidCuitError

        return cls(number)

    @classmethod
    def _check_digit_matches(cls, number):
        total = sum(
            int(digit) * weight
            for digit, weight in zip(number[:-1], cls.weights, strict=True)
        )
        check = cls.modulus - (total % cls.modulus)

        if check == cls.modulus:
            check = 0
        elif check == cls.modulus - 1:
            check = cls.replaced_check

        return check == int(number[-1])


@dataclass(frozen=True)
class OpeningHours:
    slot: dict[str, TimeSlot]
    weekday = 'weekday'
    saturday = 'saturday'
    sunday = 'sunday'
    days = (weekday, saturday, sunday)
    saturday_index = 5
    sunday_index = 6

    def __init__(self, slots=None, *, slot=None):
        if slot is None:
            slot = {item.name: item for item in slots}
        object.__setattr__(self, 'slot', slot)

    @classmethod
    def create(cls, slots):
        return cls(tuple(slots))

    @property
    def slots(self):
        return tuple(self.slot.values())

    @classmethod
    def day_name(cls, moment):
        if moment.weekday() == cls.saturday_index:
            return cls.saturday
        if moment.weekday() == cls.sunday_index:
            return cls.sunday
        return cls.weekday

    def slot_at(self, moment):
        return self.slot.get(self.day_name(moment))

    def format(self, moment):
        slot = self.slot_at(moment)
        if slot is None:
            return 'Cerrado'
        return slot.format()


@dataclass(frozen=True)
class DeliveryTerms:
    pickup: bool
    home_delivery: bool | None
    base_cost: Money | None

    @classmethod
    def create(cls, *, pickup, home_delivery, base_cost):
        if base_cost is not None and not isinstance(base_cost, Money):
            raise InvalidDeliveryTermsError

        if home_delivery is None:
            return cls(pickup=pickup, home_delivery=None, base_cost=None)

        if not home_delivery:
            if base_cost is not None:
                raise DeliveryCostWithoutHomeDeliveryError
            if not pickup:
                raise InvalidDeliveryTermsError
            return cls(pickup=pickup, home_delivery=False, base_cost=None)

        return cls(pickup=pickup, home_delivery=True, base_cost=base_cost)


class PharmacyQuerySet(models.QuerySet):
    def within(self, origin: Coordinates, radius_km: int) -> Self:
        origin = Point(origin.longitude, origin.latitude, srid=GEO_WGS84_LAT_LONG)
        return (
            self.filter(coordinates__distance_lte=(origin, D(km=radius_km)))
            .annotate(distance=Distance('coordinates', origin))
            .order_by('distance')
        )

    def open_at(self, moment):
        day = OpeningHours.day_name(moment)
        clock = f'{moment:%H:%M}'
        return self.annotate(
            opens_at=Cast(
                KeyTextTransform(
                    'opens',
                    KeyTextTransform(day, KeyTextTransform('slot', '_opening_hours')),
                ),
                CharField(),
            ),
            closes_at=Cast(
                KeyTextTransform(
                    'closes',
                    KeyTextTransform(day, KeyTextTransform('slot', '_opening_hours')),
                ),
                CharField(),
            ),
        ).filter(opens_at__lte=clock, closes_at__gte=clock)


class Pharmacy(models.Model):
    visible = models.BooleanField(default=False)

    kind = models.CharField(max_length=32, choices=PharmacyKind.choices, blank=True)

    trade_name = models.CharField(max_length=150, blank=True)

    request_email = models.EmailField(blank=True)

    _phone = models.CharField(max_length=20, blank=True, db_column='phone')

    website = models.URLField(blank=True)

    _location = models.JSONField(default=dict, blank=True, db_column='location')

    coordinates = PointField(srid=GEO_WGS84_LAT_LONG, null=True, blank=True)

    _opening_hours = models.JSONField(
        default=dict,
        blank=True,
        db_column='opening_hours',
    )

    _delivery_terms = models.JSONField(
        default=dict,
        blank=True,
        db_column='delivery_terms',
    )

    _preparation_tags = models.JSONField(
        default=list,
        blank=True,
        db_column='preparation_tags',
    )

    objects = PharmacyQuerySet.as_manager()

    def __str__(self):
        return self.trade_name or f'Farmacia {self.pk}'

    @property
    def phone(self):
        if not self._phone:
            return None
        return PhoneNumber(self._phone)

    @property
    def location(self) -> Location:
        return from_dict(Location, self._location)

    @property
    def opening_hours(self) -> OpeningHours | None:
        return from_dict(OpeningHours, self._opening_hours)

    @property
    def delivery_terms(self) -> DeliveryTerms:
        return from_dict(DeliveryTerms, self._delivery_terms)

    @property
    def preparation_tags(self) -> set[PreparationTag]:
        return {PreparationTag(tag) for tag in self._preparation_tags}

    @property
    def is_laboratory(self):
        return self.kind == PharmacyKind.PREPARATION_LAB

    def update_establishment(self, kind, trade_name):

        if self.visible and not (trade_name or '').strip():
            raise PharmacyCantClearSearchData

        self.kind = kind
        self.trade_name = trade_name

    def set_visibility(self, visible):
        if not visible:
            self.visible = False
            return

        location = self.location
        if (
            not self.trade_name.strip()
            or not self.request_email.strip()
            or location is None
            or location.coordinates is None
            or self.coordinates is None
        ):
            raise PharmacyCantBecomeVisible

        self.visible = True

    def update_contact_info(self, request_email, phone, website):

        if self.visible and not (request_email or '').strip():
            raise PharmacyCantClearSearchData

        self.request_email = request_email
        self._phone = phone.number if phone else ''
        self.website = website

    def update_location(self, location):

        if self.visible and (location is None or location.coordinates is None):
            raise PharmacyCantClearSearchData

        if location is None:
            self._location = {}
            self.coordinates = None
            return

        self._location = asdict(location)

        if location.coordinates is None:
            self.coordinates = None
            return

        self.coordinates = Point(
            location.coordinates.longitude,
            location.coordinates.latitude,
            srid=GEO_WGS84_LAT_LONG,
        )

    def update_opening_hours(self, opening_hours):
        self._opening_hours = asdict(opening_hours) if opening_hours else {}

    def update_delivery_terms(self, delivery_terms):
        self._delivery_terms = asdict(delivery_terms) if delivery_terms else {}

    def update_preparation_tags(self, preparation_tags: set[PreparationTag]):
        self._preparation_tags = sorted(tag.value for tag in preparation_tags)


class PharmacyAccount(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='pharmacy_account',
    )

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        related_name='accounts',
    )

    legal_name = models.CharField(max_length=150, blank=True)

    _cuit = models.CharField(max_length=11, blank=True, db_column='cuit')

    technical_director = models.CharField(max_length=150, blank=True)

    license = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return self.pharmacy.trade_name or self.user.email

    @property
    def cuit(self):
        if not self._cuit:
            return None
        return Cuit(self._cuit)

    def update_legal_info(
        self,
        legal_name,
        cuit,
        technical_director,
        license,  # noqa: A002
    ):
        self.legal_name = legal_name
        self._cuit = cuit.number if cuit else ''
        self.technical_director = technical_director
        self.license = license
