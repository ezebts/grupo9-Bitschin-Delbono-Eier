from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Cliente'
        PHARMACY = 'pharmacy', 'Farmacia o laboratorio'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_pharmacy(self):
        return self.role == self.Role.PHARMACY

    def get_initials(self):
        return ''.join(
            name[0] for name in (self.first_name, self.last_name) if name
        ).upper()
