from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import User
from chats.queries.customer_inbox import get_customer_conversation
from chats.queries.pharmacy_inbox import get_conversation, get_pharmacy_inbox
from chats.tests.support import open_conversation
from orders.commands.save_quote import QuoteTerms, save_quote
from orders.commands.withdraw_quote import withdraw_quote
from orders.exceptions import (
    QuoteCannotBeEditedError,
    QuoteCannotBeWithdrawnError,
)
from orders.models import DeliveryPreference, QuoteRequest, QuoteRequestStatus

pytestmark = pytest.mark.django_db


def _user(email, role):
    user = User(username=email, email=email, role=role)
    user.set_unusable_password()
    user.save()
    return user


def _terms(
    *,
    price='18400',
    preparation_time='48 h hábiles',
    delivery_preferences=(DeliveryPreference.PICKUP,),
    delivery_cost=Decimal(0),
):
    return QuoteTerms(
        price=Decimal(price),
        preparation_time=preparation_time,
        delivery_preferences=delivery_preferences,
        delivery_cost=delivery_cost,
        valid_until=timezone.localdate() + timedelta(days=7),
    )


def _assert_raises(error_type, callback):
    try:
        callback()
    except error_type:
        return
    pytest.fail(f'Expected {error_type.__name__} to be raised.')


def test_pharmacy_can_send_and_edit_a_quote_for_its_conversation():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)

    quote = save_quote(pharmacy_user.id, conversation.id, _terms())
    assert quote.status == QuoteRequestStatus.QUOTED
    assert quote.price == Decimal(18400)
    assert quote.preparation_time == '48 h hábiles'

    updated = save_quote(
        pharmacy_user.id,
        conversation.id,
        _terms(price='19500', preparation_time='72 h hábiles'),
    )
    assert updated.status == QuoteRequestStatus.QUOTED
    assert updated.price == Decimal(19500)
    assert updated.preparation_time == '72 h hábiles'

    conversation.refresh_from_db()
    assert list(conversation.messages.values_list('body', flat=True)) == [
        'La farmacia envió un presupuesto.',
        'La farmacia actualizó el presupuesto.',
    ]

    customer_chat = get_customer_conversation(
        customer.id,
        conversation.quote_request.order_id,
        conversation.id,
    )
    assert customer_chat.quote_price == Decimal(19500)
    assert customer_chat.preparation_time == '72 h hábiles'

    pharmacy_chat = get_conversation(pharmacy_user.id, conversation.id)
    assert pharmacy_chat.quote_price == Decimal(19500)
    assert not pharmacy_chat.waiting_for_pharmacy
    assert not get_pharmacy_inbox(pharmacy_user.id, unread_only=True).conversations


def test_pharmacy_can_withdraw_only_its_unaccepted_quote():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)
    save_quote(pharmacy_user.id, conversation.id, _terms())

    withdrawn = withdraw_quote(pharmacy_user.id, conversation.id)
    assert withdrawn.status == QuoteRequestStatus.WITHDRAWN

    conversation.refresh_from_db()
    assert conversation.messages.last().body == 'La farmacia retiró el presupuesto.'
    customer_chat = get_customer_conversation(
        customer.id,
        conversation.quote_request.order_id,
        conversation.id,
    )
    assert customer_chat.quote_status == QuoteRequestStatus.WITHDRAWN

    _assert_raises(
        QuoteCannotBeEditedError,
        lambda: save_quote(pharmacy_user.id, conversation.id, _terms()),
    )
    _assert_raises(
        QuoteCannotBeWithdrawnError,
        lambda: withdraw_quote(pharmacy_user.id, conversation.id),
    )


def test_quote_can_offer_pickup_and_home_delivery_with_a_delivery_fee():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(
        customer,
        pharmacy_user,
        delivery_preferences=(
            DeliveryPreference.PICKUP,
            DeliveryPreference.HOME_DELIVERY,
        ),
    )

    quote = save_quote(
        pharmacy_user.id,
        conversation.id,
        _terms(
            delivery_preferences=(
                DeliveryPreference.PICKUP,
                DeliveryPreference.HOME_DELIVERY,
            ),
            delivery_cost=Decimal(2500),
        ),
    )

    assert quote.delivery_preferences == (
        DeliveryPreference.PICKUP,
        DeliveryPreference.HOME_DELIVERY,
    )
    assert quote.delivery_cost == Decimal(2500)


def test_pharmacy_cannot_change_another_pharmacy_quote():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    other_user = _user('otra-farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)

    _assert_raises(
        QuoteRequest.DoesNotExist,
        lambda: save_quote(other_user.id, conversation.id, _terms()),
    )


def test_pharmacy_cannot_edit_or_withdraw_an_accepted_quote():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)
    save_quote(pharmacy_user.id, conversation.id, _terms())
    quote_request = conversation.quote_request
    quote_request.status = QuoteRequestStatus.ACCEPTED
    quote_request.save(update_fields=['status'])

    _assert_raises(
        QuoteCannotBeEditedError,
        lambda: save_quote(pharmacy_user.id, conversation.id, _terms()),
    )
    _assert_raises(
        QuoteCannotBeWithdrawnError,
        lambda: withdraw_quote(pharmacy_user.id, conversation.id),
    )
