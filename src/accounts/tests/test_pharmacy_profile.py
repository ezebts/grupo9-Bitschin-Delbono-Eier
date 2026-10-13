from dataclasses import replace
from datetime import time

import pytest

from accounts.commands.set_pharmacy_visibility import set_pharmacy_visibility
from accounts.commands.update_pharmacy_profile import (
    UpdatePharmacyProfileParams,
    update_pharmacy_profile,
)
from accounts.exceptions import (
    PharmacyCantBecomeVisible,
    PharmacyCantClearSearchData,
)
from accounts.models import (
    Cuit,
    DeliveryTerms,
    OpeningHours,
    Pharmacy,
    PharmacyAccount,
    PharmacyMailPreferences,
    PreparationTag,
    User,
)
from shared.values import Coordinates, Location, Money, PhoneNumber, TimeSlot

pytestmark = pytest.mark.django_db


@pytest.fixture(scope='module')
def pharmacy_profile_params():
    return UpdatePharmacyProfileParams(
        first_name='María',
        last_name='López',
        kind='pharmacy_with_lab',
        trade_name='Farmacia Galénica',
        legal_name='Galénica SRL',
        cuit=Cuit.create('30712345671'),
        technical_director='María López',
        license='MN 12345',
        request_email='pedidos@galenica.test',
        phone=PhoneNumber.AR('1144445555'),
        website='https://galenica.test',
        location=Location.create(
            'Av. Santa Fe 3820',
            'Palermo',
            '1425',
            Coordinates.create(-34.5842582, -58.4174826),
        ),
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
            base_cost=Money.ARS(1500),
        ),
        preparation_tags={PreparationTag.CAPSULES, PreparationTag.CREAMS},
        mail_preferences=PharmacyMailPreferences(
            on_reply=False,
            on_quote_status=True,
        ),
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
    return PharmacyAccount.objects.create(
        user=user,
        pharmacy=Pharmacy.objects.create(),
    )


def test_pharmacy_updates_profile(pharmacy_account, pharmacy_profile_params):
    pharmacy_account.pharmacy.visible = True
    pharmacy_account.pharmacy.save(update_fields=['visible'])

    update_pharmacy_profile(pharmacy_account.user_id, pharmacy_profile_params)

    pharmacy_account.refresh_from_db()
    pharmacy = pharmacy_account.pharmacy
    pharmacy.refresh_from_db()
    user = pharmacy_account.user
    user.refresh_from_db()

    assert pharmacy.visible
    assert user.first_name == pharmacy_profile_params.first_name
    assert user.last_name == pharmacy_profile_params.last_name
    assert pharmacy.kind == pharmacy_profile_params.kind
    assert pharmacy.trade_name == pharmacy_profile_params.trade_name
    assert pharmacy_account.legal_name == pharmacy_profile_params.legal_name
    assert (
        pharmacy_account.technical_director
        == pharmacy_profile_params.technical_director
    )
    assert pharmacy_account.license == pharmacy_profile_params.license
    assert pharmacy_account.cuit == pharmacy_profile_params.cuit

    assert pharmacy.request_email == pharmacy_profile_params.request_email
    assert pharmacy.phone == pharmacy_profile_params.phone
    assert pharmacy.website == pharmacy_profile_params.website

    assert pharmacy.location == pharmacy_profile_params.location
    assert pharmacy.coordinates.x == pytest.approx(-58.4174826)
    assert pharmacy.coordinates.y == pytest.approx(-34.5842582)

    assert pharmacy.opening_hours == pharmacy_profile_params.opening_hours

    assert pharmacy.delivery_terms == pharmacy_profile_params.delivery_terms

    assert pharmacy.preparation_tags == pharmacy_profile_params.preparation_tags
    assert pharmacy.mail_preferences == pharmacy_profile_params.mail_preferences


def test_pharmacy_becomes_visible_when_it_can_be_found(
    pharmacy_account,
    pharmacy_profile_params,
):
    update_pharmacy_profile(pharmacy_account.user_id, pharmacy_profile_params)

    set_pharmacy_visibility(pharmacy_account.user_id, visible=True)

    pharmacy_account.pharmacy.refresh_from_db()
    assert pharmacy_account.pharmacy.visible


def test_pharmacy_stays_hidden_without_a_mapped_location(
    pharmacy_account,
    pharmacy_profile_params,
):
    update_pharmacy_profile(
        pharmacy_account.user_id,
        replace(
            pharmacy_profile_params,
            location=Location.create('Av. Santa Fe 3820', 'Palermo', '1425'),
        ),
    )

    with pytest.raises(PharmacyCantBecomeVisible):
        set_pharmacy_visibility(pharmacy_account.user_id, visible=True)

    pharmacy_account.pharmacy.refresh_from_db()
    assert not pharmacy_account.pharmacy.visible


@pytest.mark.parametrize(
    'cleared',
    [
        {'trade_name': '   '},
        {'request_email': ''},
        {'location': None},
        {'location': Location.create('Av. Santa Fe 3820', 'Palermo', '1425')},
    ],
)
def test_visible_pharmacy_keeps_the_data_clients_search_with(
    pharmacy_account,
    pharmacy_profile_params,
    cleared,
):
    update_pharmacy_profile(pharmacy_account.user_id, pharmacy_profile_params)
    set_pharmacy_visibility(pharmacy_account.user_id, visible=True)

    with pytest.raises(PharmacyCantClearSearchData):
        update_pharmacy_profile(
            pharmacy_account.user_id,
            replace(pharmacy_profile_params, **cleared),
        )

    pharmacy_account.pharmacy.refresh_from_db()
    assert pharmacy_account.pharmacy.visible
    assert pharmacy_account.pharmacy.trade_name == pharmacy_profile_params.trade_name
    assert (
        pharmacy_account.pharmacy.request_email == pharmacy_profile_params.request_email
    )
    assert pharmacy_account.pharmacy.location == pharmacy_profile_params.location


def test_pharmacy_clears_optional_profile_data(
    pharmacy_account,
    pharmacy_profile_params,
):
    update_pharmacy_profile(pharmacy_account.user_id, pharmacy_profile_params)
    update_pharmacy_profile(
        pharmacy_account.user_id,
        replace(
            pharmacy_profile_params,
            kind='',
            trade_name='',
            legal_name='',
            cuit=None,
            technical_director='',
            license='',
            request_email='',
            phone=None,
            website='',
            location=None,
            opening_hours=None,
            delivery_terms=None,
            preparation_tags=set(),
        ),
    )

    pharmacy_account.refresh_from_db()
    pharmacy = pharmacy_account.pharmacy
    pharmacy.refresh_from_db()

    assert pharmacy.kind == ''
    assert pharmacy.trade_name == ''
    assert pharmacy.request_email == ''
    assert pharmacy.phone is None
    assert pharmacy.website == ''
    assert pharmacy.location is None
    assert pharmacy.coordinates is None
    assert pharmacy.opening_hours is None
    assert pharmacy.delivery_terms is None
    assert pharmacy.preparation_tags == set()
    assert pharmacy_account.legal_name == ''
    assert pharmacy_account.cuit is None
    assert pharmacy_account.technical_director == ''
    assert pharmacy_account.license == ''
