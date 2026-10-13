import csv
from datetime import time
from pathlib import Path

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.commands.set_pharmacy_visibility import set_pharmacy_visibility
from accounts.commands.signup import signup
from accounts.commands.update_pharmacy_profile import (
    UpdatePharmacyProfileParams,
    update_pharmacy_profile,
)
from accounts.models import (
    DeliveryTerms,
    OpeningHours,
    PharmacyMailPreferences,
    PreparationTag,
    User,
)
from shared.values import Coordinates, Location, Money, PhoneNumber, TimeSlot

DEMO_PHARMACIES = Path(__file__).with_name('demo_pharmacies.csv')

# Weekday, saturday and sunday hours; None means closed.
HOURS = {
    'store': (('08:00', '20:00'), ('09:00', '13:00'), None),
    'long': (('07:30', '22:00'), ('08:00', '22:00'), ('09:00', '13:00')),
    'always': (('00:00', '23:59'), ('00:00', '23:59'), ('00:00', '23:59')),
    'lab': (('08:00', '16:00'), None, None),
}


def _opening_hours(profile):
    slots = []
    for day, hours in zip(OpeningHours.days, HOURS[profile], strict=True):
        opens, closes = map(time.fromisoformat, hours) if hours else (None, None)
        slots.append(TimeSlot.create(day, opens=opens, closes=closes))
    return OpeningHours.create(slots)


def _delivery_terms(cost):
    if not cost:
        return DeliveryTerms.create(pickup=True, home_delivery=False, base_cost=None)
    return DeliveryTerms.create(
        pickup=True,
        home_delivery=True,
        base_cost=Money.ARS(cost),
    )


class Command(BaseCommand):
    help = 'Creates the demo pharmacies around Rafaela, Santa Fe.'

    def handle(self, *args, **options):  # noqa: ARG002
        password = settings.DEMO_PHARMACY_PASSWORD
        if not password:
            self.stdout.write('DEMO_PHARMACY_PASSWORD is not set; skipping.')
            return

        with DEMO_PHARMACIES.open(encoding='utf-8') as file:
            rows = list(csv.DictReader(file))

        for number, row in enumerate(rows, start=1):
            self.seed(number, row, password)

        self.stdout.write(f'{len(rows)} demo pharmacies are ready.')

    @transaction.atomic
    def seed(self, number, row, password):
        name = row['name']
        email = f'farmacia{number:02d}@example.com'

        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name='Responsable',
                last_name=name,
            )
            EmailAddress.objects.create(
                user=user,
                email=email,
                primary=True,
                verified=True,
            )
            signup(user, User.Role.PHARMACY)

        update_pharmacy_profile(
            user.id,
            UpdatePharmacyProfileParams(
                first_name='Responsable',
                last_name=name,
                kind=row['kind'],
                trade_name=name,
                legal_name=f'{name} S.R.L.',
                cuit=None,
                technical_director='Farm. Demo',
                license=f'MP {1000 + number}',
                request_email=email,
                phone=PhoneNumber.AR(f'3492{400000 + number * 37:06d}'),
                website='',
                location=Location.create(
                    row['address'],
                    row['locality'],
                    row['postal_code'],
                    Coordinates.create(row['latitude'], row['longitude']),
                ),
                opening_hours=_opening_hours(row['hours']),
                delivery_terms=_delivery_terms(row['delivery_cost']),
                preparation_tags={
                    PreparationTag(tag) for tag in row['preparations'].split()
                },
                mail_preferences=PharmacyMailPreferences(
                    on_reply=False,
                    on_quote_status=False,
                ),
            ),
        )
        set_pharmacy_visibility(user.id, visible=True)
