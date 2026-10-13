from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

from django.contrib.auth.models import AbstractUser
from django.core import signing
from django.db import models
from django.urls import reverse

from accounts.exceptions import InvalidInvitationLinkError
from shared.dataclasses import asdict, from_dict


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Cliente'
        PHARMACY = 'pharmacy', 'Farmacia o laboratorio'

    defaulttz = 'America/Argentina/Buenos_Aires'

    first_name = models.CharField('first name', max_length=150)

    last_name = models.CharField('last name', max_length=150)

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    _timezone = models.CharField(
        max_length=64,
        blank=True,
        default=defaulttz,
        db_column='timezone',
    )

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_pharmacy(self):
        return self.role == self.Role.PHARMACY

    @property
    def timezone(self):
        return ZoneInfo(self._timezone or self.defaulttz)

    def get_initials(self):
        return ''.join(
            name[0] for name in (self.first_name, self.last_name) if name
        ).upper()


@dataclass(frozen=True)
class InvitationLink:
    role: User.Role
    email: str
    next_url: str = ''
    details: dict = field(default_factory=dict)
    _value: str = field(default='', compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, 'role', User.Role(self.role))

    def __str__(self) -> str:

        if self._value:
            return self._value

        payload = asdict(self)
        payload.pop('_value', None)
        signed = signing.dumps(payload)
        link = f'{reverse("invitation")}?{urlencode({"_invitation": signed})}'

        object.__setattr__(self, '_value', link)

        return self._value

    @classmethod
    def from_value(cls, invitation_link: str):

        try:
            signed = invitation_link
            if '_invitation=' in invitation_link:
                signed = parse_qs(urlparse(invitation_link).query)['_invitation'][0]

            link = from_dict(cls, signing.loads(signed))

            if link is None:
                raise InvalidInvitationLinkError

        except (signing.BadSignature, KeyError, TypeError, ValueError) as error:
            raise InvalidInvitationLinkError from error

        if '_invitation=' in invitation_link:
            object.__setattr__(link, '_value', invitation_link)

        return link
