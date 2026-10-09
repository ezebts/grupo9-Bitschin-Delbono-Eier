from dataclasses import dataclass
from enum import Enum

from django.db import models

from accounts.models.base import User
from shared.dataclasses import asdict, from_dict
from shared.values import Location, PhoneNumber


@dataclass(frozen=True)
class MailPreferences:
    on_reply: bool
    on_status_change: bool
    on_quote_expiry: bool


class SearchRadius(int, Enum):
    KM1 = 1
    KM3 = 3
    KM5 = 5
    KM10 = 10


def default_mail_preferences():
    return asdict(
        MailPreferences(
            on_reply=True,
            on_status_change=True,
            on_quote_expiry=True,
        ),
    )


class ClientAccount(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='client_account',
    )

    _phone = models.CharField(max_length=20, blank=True, db_column='phone')

    health_insurance_number = models.CharField(max_length=40, blank=True)

    _location = models.JSONField(default=dict, blank=True, db_column='location')

    search_radius = models.PositiveSmallIntegerField(null=True, blank=True)

    _mail_preferences = models.JSONField(
        default=default_mail_preferences,
        blank=True,
        db_column='mail_preferences',
    )

    def __str__(self):
        return self.user.get_full_name() or self.user.email

    @property
    def phone(self):
        if not self._phone:
            return None
        return PhoneNumber(self._phone)

    @property
    def location(self) -> Location:
        return from_dict(Location, self._location)

    @property
    def mail_preferences(self) -> MailPreferences:
        return from_dict(MailPreferences, self._mail_preferences)

    def update_personal_details(self, phone, health_insurance_number):
        self._phone = phone.number
        self.health_insurance_number = health_insurance_number

    def update_search_preferences(self, location, search_radius):
        self._location = asdict(location)
        self.search_radius = search_radius

    def update_mail_preferences(self, mail_preferences):
        self._mail_preferences = asdict(mail_preferences)
