from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from accounts.models import PharmacyAccount, PharmacyKind, SearchRadius, User
from accounts.queries.find_nearby_pharmacies import find_nearby_pharmacies
from accounts.tests.test_find_nearby_pharmacies import (
    ARGENTINA,
    NEAR,
    ORIGIN,
    _pharmacy,
)
from chats.tests.support import open_conversation
from orders.commands.accept_quote import accept_quote
from orders.commands.advance_order import AdvanceOrderParams, advance_order
from orders.commands.submit_quote import submit_quote
from orders.tests.test_order_fulfillment import _accepted_order, _in_days
from orders.tests.test_quote_management import _assert_raises, _params, _user
from reviews.commands.submit_review import submit_review
from reviews.exceptions import ReviewAlreadySentError, ReviewNotAllowedError
from reviews.forms import ReviewForm
from reviews.models import COMMENT_MAX_LENGTH, Review
from shared.values import Location

pytestmark = pytest.mark.django_db


def _delivered():
    customer, pharmacy_user, _order, conversation = _accepted_order()
    advance_order(pharmacy_user.id, conversation.id, _in_days(pharmacy_user, 1))
    advance_order(pharmacy_user.id, conversation.id, AdvanceOrderParams(None))
    advance_order(pharmacy_user.id, conversation.id, AdvanceOrderParams(None))
    return customer, pharmacy_user, conversation


def test_a_client_reviews_a_delivered_order_once():
    customer, _pharmacy_user, conversation = _delivered()
    customer.first_name = 'Sofia'
    customer.last_name = 'Paz'
    customer.save(update_fields=['first_name', 'last_name'])

    submit_review(customer.id, conversation.id, 4, '  Muy clara.  ')

    pharmacy = conversation.quote_request.pharmacy
    pharmacy.refresh_from_db()
    assert pharmacy.score == Decimal('4.0')
    assert Review.objects.get().comment == 'Muy clara.'
    _assert_raises(
        ReviewAlreadySentError,
        lambda: submit_review(customer.id, conversation.id, 5, ''),
    )


def test_pharmacy_score_is_the_average_of_its_reviews():
    _customer, pharmacy_user, first = _delivered()
    submit_review(_customer.id, first.id, 5, '')

    customer = _user('otro@example.com', User.Role.CUSTOMER)
    _order, second = open_conversation(customer, pharmacy_user, formula='Jarabe')
    submit_quote(pharmacy_user.id, second.id, _params())
    accept_quote(customer.id, second.id)
    advance_order(pharmacy_user.id, second.id, _in_days(pharmacy_user, 1))
    advance_order(pharmacy_user.id, second.id, AdvanceOrderParams(None))
    advance_order(pharmacy_user.id, second.id, AdvanceOrderParams(None))
    submit_review(customer.id, second.id, 4, 'Rápida')

    pharmacy = PharmacyAccount.objects.get(user=pharmacy_user).pharmacy
    pharmacy.refresh_from_db()
    assert pharmacy.score == Decimal('4.5')


def test_only_a_delivered_order_can_be_reviewed():
    customer, _pharmacy_user, _order, conversation = _accepted_order()

    _assert_raises(
        ReviewNotAllowedError,
        lambda: submit_review(customer.id, conversation.id, 5, ''),
    )


@pytest.mark.parametrize('score', [0, 6])
def test_review_score_stays_between_1_and_5(score):
    customer, _pharmacy_user, conversation = _delivered()

    with pytest.raises(IntegrityError), transaction.atomic():
        submit_review(customer.id, conversation.id, score, '')


def test_review_form_rejects_a_comment_over_the_field_limit():
    form = ReviewForm(
        data={'score': 5, 'comment': 'a' * (COMMENT_MAX_LENGTH + 1)},
    )

    assert not form.is_valid()
    assert str(COMMENT_MAX_LENGTH) in form.errors['comment'][0]


def test_search_keeps_pharmacies_at_or_above_the_minimum_score():
    customer, _pharmacy_user, conversation = _delivered()
    customer.first_name = 'Sofia'
    customer.last_name = 'Paz'
    customer.save(update_fields=['first_name', 'last_name'])
    pharmacy = conversation.quote_request.pharmacy
    pharmacy.kind = PharmacyKind.PHARMACY_WITH_LAB
    pharmacy.update_location(Location.create('Calle 100', 'Palermo', '1425', NEAR))
    pharmacy.save()
    submit_review(customer.id, conversation.id, 5, 'Excelente')

    low = _pharmacy(
        'baja@example.com',
        point=NEAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
    )
    low.score = Decimal('3.0')
    low.save(update_fields=['score'])
    unreviewed = _pharmacy(
        'nueva@example.com',
        point=NEAR,
        kind=PharmacyKind.PHARMACY_WITH_LAB,
    )

    search = {
        'radius_km': SearchRadius.create(3),
        'include_pharmacies': True,
        'include_labs': True,
        'open_now': False,
        'home_delivery': False,
        'timezone': ARGENTINA,
    }
    listed = find_nearby_pharmacies(ORIGIN, **search)
    untouched = next(item for item in listed if item.id == unreviewed.pk)
    assert untouched.score is None
    assert untouched.reviews == ()

    found = find_nearby_pharmacies(ORIGIN, **search, min_score=4)

    assert [item.id for item in found] == [pharmacy.pk]
    assert found[0].score == Decimal('5.0')
    assert found[0].reviews[0].initials == 'SP'
    assert found[0].reviews[0].name == 'Sofia Paz'
    assert found[0].reviews[0].comment == 'Excelente'
    assert found[0].reviews[0].created_at == Review.objects.get().created_at
    assert low.pk not in [item.id for item in found]
