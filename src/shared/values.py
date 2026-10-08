import math
import re
from dataclasses import dataclass
from datetime import time
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum

from django.utils.translation import gettext_lazy as _

from shared.exceptions import Error


@dataclass(frozen=True)
class InvalidPhoneNumberError(Error):
    message = _('Ingresá un teléfono válido, con código de área.')


@dataclass(frozen=True)
class PhoneNumber:
    number: str
    min_digits = 10
    max_digits = 13

    @classmethod
    def AR(cls, raw):  # noqa: N802
        digits = re.sub(r'\D', '', raw or '')

        if not cls.min_digits <= len(digits) <= cls.max_digits:
            raise InvalidPhoneNumberError

        return cls(digits)


@dataclass(frozen=True)
class InvalidCoordinatesError(Error):
    message = _('Ingresá una latitud y una longitud válidas.')


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float
    min_latitude = -90
    max_latitude = 90
    min_longitude = -180
    max_longitude = 180

    @classmethod
    def create(cls, latitude, longitude):
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            raise InvalidCoordinatesError

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            raise InvalidCoordinatesError from None

        latitude_is_invalid = (
            not math.isfinite(latitude)
            or not cls.min_latitude <= latitude <= cls.max_latitude
        )

        longitude_is_invalid = (
            not math.isfinite(longitude)
            or not cls.min_longitude <= longitude <= cls.max_longitude
        )

        if latitude_is_invalid or longitude_is_invalid:
            raise InvalidCoordinatesError

        return cls(latitude, longitude)


@dataclass(frozen=True)
class IncompleteLocationError(Error):
    message = _('Completá la dirección, la localidad y un código postal válido.')


@dataclass(frozen=True)
class Location:
    address: str
    locality: str
    postal_code: str
    coordinates: Coordinates | None = None
    postal_code_max_length = 8
    postal_code_pattern = re.compile(r'^\d{4}$|^[A-HJ-NP-Za-hj-np-z]\d{4}[A-Za-z]{3}$')

    @classmethod
    def create(cls, address, locality, postal_code, coordinates=None):
        address = (address or '').strip()
        locality = (locality or '').strip()
        postal_code = (postal_code or '').strip()

        if not cls.postal_code_pattern.fullmatch(postal_code):
            raise IncompleteLocationError

        if len(postal_code) == cls.postal_code_max_length:
            postal_code = (
                f'{postal_code[0].upper()}{postal_code[1:5]}{postal_code[5:].upper()}'
            )

        if not address or not locality:
            raise IncompleteLocationError

        if coordinates is not None and not isinstance(coordinates, Coordinates):
            raise InvalidCoordinatesError

        return cls(address, locality, postal_code, coordinates)


@dataclass(frozen=True)
class InvalidTimeSlotError(Error):
    message = _('Indicá apertura y cierre, o marcalo como cerrado.')


@dataclass(frozen=True)
class TimeSlot:
    name: str
    opens: time | None
    closes: time | None

    @classmethod
    def create(cls, name, *, opens, closes):
        if opens is None and closes is None:
            return cls(name, opens=None, closes=None)

        if opens is None or closes is None or opens >= closes:
            raise InvalidTimeSlotError

        return cls(name, opens=opens, closes=closes)

    @property
    def closed(self):
        return self.opens is None


@dataclass(frozen=True)
class InvalidMoneyError(Error):
    message = _('Ingresá un monto válido, cero o mayor.')


@dataclass(frozen=True)
class Money:
    class Currency(StrEnum):
        ARS = 'ARS'
        USD = 'USD'

    amount: Decimal

    currency: Currency

    decimal_places: int

    rounding: str = ROUND_HALF_EVEN

    max_digits = 12

    @staticmethod
    def _digit_count(amount):
        digits = format(amount, 'f').replace('.', '').lstrip('-').lstrip('0')
        return len(digits or '0')

    def __post_init__(self):

        currency = self.Currency(self.currency)

        if self.decimal_places < 0:
            raise InvalidMoneyError

        try:
            raw_decimal = Decimal(str(self.amount))

            amount = raw_decimal.quantize(
                exp=Decimal(10) ** -self.decimal_places,
                rounding=self.rounding,
            )

        except (InvalidOperation, ValueError, TypeError) as error:
            raise InvalidMoneyError from error

        if not amount.is_finite() or amount < 0:
            raise InvalidMoneyError

        if self._digit_count(amount) > self.max_digits:
            raise InvalidMoneyError

        object.__setattr__(self, 'amount', amount)
        object.__setattr__(self, 'currency', currency)

    @classmethod
    def ARS(cls, amount=0):  # noqa: N802
        return cls(amount=amount, currency=cls.Currency.ARS, decimal_places=2)

    @classmethod
    def USD(cls, amount=0):  # noqa: N802
        return cls(amount=amount, currency=cls.Currency.USD, decimal_places=2)

    @classmethod
    def create(cls, currency, amount=0):
        constructors = {
            cls.Currency.ARS: cls.ARS,
            cls.Currency.USD: cls.USD,
        }

        return constructors[cls.Currency(currency)](amount)
