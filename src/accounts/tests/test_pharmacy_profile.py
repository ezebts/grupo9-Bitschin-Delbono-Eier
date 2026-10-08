from datetime import time

import pytest

from accounts.commands.update_pharmacy_profile import (
    UpdatePharmacyProfileParams,
    update_pharmacy_profile,
)
from accounts.models import (
    Cuit,
    DeliveryRadius,
    DeliveryTerms,
    OpeningHours,
    PharmacyAccount,
    PreparationTag,
    User,
)
from shared.values import Location, Money, PhoneNumber, TimeSlot

pytestmark = pytest.mark.django_db


@pytest.fixture(scope='module')
def pharmacy_profile_params():
    return UpdatePharmacyProfileParams(
        visible=False,
        kind='pharmacy_with_lab',
        trade_name='Farmacia Galénica',
        legal_name='Galénica SRL',
        cuit=Cuit.create('30712345671'),
        technical_director='María López',
        license='MN 12345',
        request_email='pedidos@galenica.test',
        phone=PhoneNumber.AR('1144445555'),
        website='https://galenica.test',
        location=Location.create('Av. Santa Fe 3820', 'Palermo', '1425'),
        opening_hours=OpeningHours(
            (
                TimeSlot.create(
                    name=OpeningHours.weekday,
                    opens=time(9, 0),
                    closes=time(21, 0),
                ),
                TimeSlot.create(
                    name=OpeningHours.saturday,
                    opens=time(9, 0),
                    closes=time(13, 0),
                ),
                TimeSlot.create(
                    name=OpeningHours.sunday,
                    opens=None,
                    closes=None,
                ),
            ),
        ),
        delivery_terms=DeliveryTerms.create(
            pickup=True,
            home_delivery=True,
            radius=DeliveryRadius.KM5,
            base_cost=Money.ARS(1500),
        ),
        preparation_tags={PreparationTag.CAPSULES, PreparationTag.CREAMS},
    )


@pytest.fixture
def pharmacy_account(db):  # noqa: ARG001
    user = User(
        username='ana@example.com',
        email='ana@example.com',
        role=User.Role.PHARMACY,
        first_name='Ana',
        last_name='Pérez',
    )
    user.set_unusable_password()
    user.save()
    return PharmacyAccount.objects.create(user=user)


def test_pharmacy_updates_profile(pharmacy_account, pharmacy_profile_params):
    update_pharmacy_profile(pharmacy_account.user_id, pharmacy_profile_params)

    pharmacy_account.refresh_from_db()

    assert pharmacy_account.visible is pharmacy_profile_params.visible
    assert pharmacy_account.kind == pharmacy_profile_params.kind
    assert pharmacy_account.trade_name == pharmacy_profile_params.trade_name
    assert pharmacy_account.legal_name == pharmacy_profile_params.legal_name
    assert (
        pharmacy_account.technical_director
        == pharmacy_profile_params.technical_director
    )
    assert pharmacy_account.license == pharmacy_profile_params.license
    assert pharmacy_account.cuit == pharmacy_profile_params.cuit

    assert pharmacy_account.request_email == pharmacy_profile_params.request_email
    assert pharmacy_account.phone == pharmacy_profile_params.phone
    assert pharmacy_account.website == pharmacy_profile_params.website

    assert pharmacy_account.location == pharmacy_profile_params.location

    assert pharmacy_account.opening_hours == pharmacy_profile_params.opening_hours

    assert pharmacy_account.delivery_terms == pharmacy_profile_params.delivery_terms

    assert pharmacy_account.preparation_tags == pharmacy_profile_params.preparation_tags
