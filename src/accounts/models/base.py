from zoneinfo import ZoneInfo

from django.contrib.auth.models import AbstractUser
from django.db import models


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
