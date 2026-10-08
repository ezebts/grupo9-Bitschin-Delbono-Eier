import re
from dataclasses import dataclass
from enum import Enum

from django.db import models

from accounts.exceptions import InvalidCuitError, InvalidDeliveryTermsError
from accounts.models.base import User
from shared.dataclasses import asdict, from_dict
from shared.values import Location, Money, PhoneNumber, TimeSlot


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
    slots: tuple[TimeSlot, ...]
    weekday = 'weekday'
    saturday = 'saturday'
    sunday = 'sunday'
    days = (weekday, saturday, sunday)


class DeliveryRadius(int, Enum):
    KM3 = 3
    KM5 = 5
    KM10 = 10


@dataclass(frozen=True)
class DeliveryTerms:
    pickup: bool
    home_delivery: bool
    radius: DeliveryRadius | None
    base_cost: Money | None

    @classmethod
    def create(cls, *, pickup, home_delivery, radius, base_cost):
        if not pickup and not home_delivery:
            raise InvalidDeliveryTermsError

        if not home_delivery:
            return cls(
                pickup=pickup,
                home_delivery=False,
                radius=None,
                base_cost=None,
            )

        try:
            distance = DeliveryRadius(radius)
        except ValueError:
            distance = None

        if distance is None:
            raise InvalidDeliveryTermsError

        if base_cost is not None and not isinstance(base_cost, Money):
            raise InvalidDeliveryTermsError

        return cls(
            pickup=pickup,
            home_delivery=True,
            radius=distance,
            base_cost=base_cost,
        )


class PharmacyAccount(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='pharmacy_account',
    )

    visible = models.BooleanField(default=True)

    kind = models.CharField(max_length=32, choices=PharmacyKind.choices, blank=True)

    trade_name = models.CharField(max_length=150, blank=True)

    legal_name = models.CharField(max_length=150, blank=True)

    _cuit = models.CharField(max_length=11, blank=True, db_column='cuit')

    technical_director = models.CharField(max_length=150, blank=True)

    license = models.CharField(max_length=40, blank=True)

    request_email = models.EmailField(blank=True)

    _phone = models.CharField(max_length=20, blank=True, db_column='phone')

    website = models.URLField(blank=True)

    _location = models.JSONField(default=dict, blank=True, db_column='location')

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

    def __str__(self):
        return self.trade_name or self.user.email

    @property
    def cuit(self):
        if not self._cuit:
            return None
        return Cuit(self._cuit)

    @property
    def phone(self):
        if not self._phone:
            return None
        return PhoneNumber(self._phone)

    @property
    def location(self) -> Location:
        return from_dict(Location, self._location)

    @property
    def opening_hours(self) -> OpeningHours:
        return from_dict(OpeningHours, self._opening_hours)

    @property
    def delivery_terms(self) -> DeliveryTerms:
        return from_dict(DeliveryTerms, self._delivery_terms)

    @property
    def preparation_tags(self) -> set[PreparationTag]:
        return {PreparationTag(tag) for tag in self._preparation_tags}

    def update_establishment(  # noqa: PLR0913, PLR0917
        self,
        visible,
        kind,
        trade_name,
        legal_name,
        cuit,
        technical_director,
        license,  # noqa: A002
    ):
        self.visible = visible
        self.kind = kind
        self.trade_name = trade_name
        self.legal_name = legal_name
        self._cuit = cuit.number
        self.technical_director = technical_director
        self.license = license

    def update_contact(self, request_email, phone, website):
        self.request_email = request_email
        self._phone = phone.number
        self.website = website

    def update_location(self, location):
        self._location = asdict(location)

    def update_opening_hours(self, opening_hours):
        self._opening_hours = asdict(opening_hours)

    def update_delivery_terms(self, delivery_terms):
        self._delivery_terms = asdict(delivery_terms)

    def update_preparation_tags(self, preparation_tags: set[PreparationTag]):
        self._preparation_tags = sorted(tag.value for tag in preparation_tags)
