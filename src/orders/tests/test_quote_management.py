from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Pharmacy, PharmacyAccount, User
from chats.queries.customer_inbox import get_customer_conversation
from chats.queries.pharmacy_inbox import get_conversation, get_pharmacy_inbox
from chats.tests.support import open_conversation
from orders.commands.accept_quote import accept_quote
from orders.commands.reject_quote import reject_quote
from orders.commands.request_quote import request_quote
from orders.commands.submit_quote import SubmitQuoteParams, submit_quote
from orders.commands.withdraw_quote import withdraw_quote
from orders.exceptions import (
    ExpiredQuoteDateError,
    ExpiredQuoteError,
    InvalidDeliveryCostError,
    InvalidQuotePriceError,
    QuoteCannotBeAnsweredError,
    QuoteCannotBeEditedError,
    QuoteCannotBeWithdrawnError,
)
from orders.models import DeliveryPreference, QuoteRequest, QuoteRequestStatus
from shared.values import Money

pytestmark = pytest.mark.django_db


def _user(email, role):
    user = User(username=email, email=email, role=role)
    user.set_unusable_password()
    user.save()
    return user


def _params(
    *,
    price='18400',
    preparation_time='48 h hábiles',
    delivery_preferences=(DeliveryPreference.PICKUP,),
    delivery_cost=0,
):
    return SubmitQuoteParams(
        price=Money.create('ARS', price),
        preparation_time=preparation_time,
        delivery_preferences=delivery_preferences,
        delivery_cost=Money.create('ARS', delivery_cost),
        valid_until=datetime.now(ZoneInfo(User.defaulttz)).date() + timedelta(days=7),
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

    quote = submit_quote(pharmacy_user.id, conversation.id, _params())
    assert quote.status == QuoteRequestStatus.QUOTED
    assert quote.price == Money.create('ARS', '18400')
    assert quote.preparation_time == '48 h hábiles'

    updated = submit_quote(
        pharmacy_user.id,
        conversation.id,
        _params(price='19500', preparation_time='72 h hábiles'),
    )
    assert updated.status == QuoteRequestStatus.QUOTED
    assert updated.price == Money.create('ARS', '19500')
    assert updated.preparation_time == '72 h hábiles'

    conversation.refresh_from_db()
    assert list(conversation.messages.values_list('body', flat=True)) == [
        'La solicitud también llega por mail',
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
    waiting = get_pharmacy_inbox(
        pharmacy_user.id,
        quote_filter=QuoteRequestStatus.WAITING,
    )
    quoted = get_pharmacy_inbox(
        pharmacy_user.id,
        quote_filter=QuoteRequestStatus.QUOTED,
    )
    assert not waiting.conversations
    assert [item.id for item in quoted.conversations] == [conversation.id]


def test_pharmacy_can_withdraw_only_its_unaccepted_quote():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)
    submit_quote(pharmacy_user.id, conversation.id, _params())

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
        lambda: submit_quote(pharmacy_user.id, conversation.id, _params()),
    )
    _assert_raises(
        QuoteCannotBeWithdrawnError,
        lambda: withdraw_quote(pharmacy_user.id, conversation.id),
    )


def test_customer_accepts_a_quote_and_the_other_pharmacies_are_not_chosen():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    other_user = _user('otra-farmacia@example.com', User.Role.PHARMACY)
    order, conversation = open_conversation(customer, pharmacy_user)
    other_pharmacy = Pharmacy.objects.create(trade_name='Otra', visible=True)
    PharmacyAccount.objects.create(user=other_user, pharmacy=other_pharmacy)
    other_request = request_quote(order.id, other_pharmacy.id)
    submit_quote(pharmacy_user.id, conversation.id, _params())

    accepted = accept_quote(customer.id, conversation.id)

    assert accepted.status == QuoteRequestStatus.ACCEPTED
    assert conversation.messages.last().body == 'El cliente aceptó el presupuesto.'
    other_request.refresh_from_db()
    assert other_request.status == QuoteRequestStatus.NOT_CHOSEN
    assert (
        other_request.conversation.messages.last().body
        == 'El cliente eligió otra farmacia.'
    )
    _assert_raises(
        QuoteCannotBeEditedError,
        lambda: submit_quote(
            other_user.id,
            other_request.conversation.id,
            _params(),
        ),
    )


def test_customer_rejects_a_quote_and_cannot_accept_it_later():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    stranger = _user('otro-cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)
    submit_quote(pharmacy_user.id, conversation.id, _params())

    _assert_raises(
        QuoteRequest.DoesNotExist,
        lambda: reject_quote(stranger.id, conversation.id),
    )

    rejected = reject_quote(customer.id, conversation.id)

    assert rejected.status == QuoteRequestStatus.REJECTED
    assert conversation.messages.last().body == 'El cliente rechazó el presupuesto.'
    _assert_raises(
        QuoteCannotBeAnsweredError,
        lambda: accept_quote(customer.id, conversation.id),
    )


def test_customer_cannot_accept_an_expired_quote():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)
    submit_quote(pharmacy_user.id, conversation.id, _params())
    QuoteRequest.objects.filter(pk=conversation.quote_request.pk).update(
        valid_until=datetime.now(customer.timezone).date() - timedelta(days=1),
    )

    _assert_raises(
        ExpiredQuoteError,
        lambda: accept_quote(customer.id, conversation.id),
    )


def test_submit_quote_rejects_a_zero_price():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)

    _assert_raises(
        InvalidQuotePriceError,
        lambda: submit_quote(
            pharmacy_user.id,
            conversation.id,
            replace(_params(), price=Money.ARS(0)),
        ),
    )


def test_submit_quote_rejects_a_valid_until_date_in_the_past():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)

    _assert_raises(
        ExpiredQuoteDateError,
        lambda: submit_quote(
            pharmacy_user.id,
            conversation.id,
            replace(
                _params(),
                valid_until=datetime.now(pharmacy_user.timezone).date()
                - timedelta(days=1),
            ),
        ),
    )


def test_submit_quote_rejects_a_zero_delivery_cost_when_home_delivery_is_offered():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(
        customer,
        pharmacy_user,
        delivery_preferences=(DeliveryPreference.HOME_DELIVERY,),
    )

    _assert_raises(
        InvalidDeliveryCostError,
        lambda: submit_quote(
            pharmacy_user.id,
            conversation.id,
            _params(
                delivery_preferences=(DeliveryPreference.HOME_DELIVERY,),
                delivery_cost=0,
            ),
        ),
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

    quote = submit_quote(
        pharmacy_user.id,
        conversation.id,
        _params(
            delivery_preferences=(
                DeliveryPreference.PICKUP,
                DeliveryPreference.HOME_DELIVERY,
            ),
            delivery_cost=2500,
        ),
    )

    assert quote.delivery_preferences == (
        DeliveryPreference.PICKUP,
        DeliveryPreference.HOME_DELIVERY,
    )
    assert quote.delivery_cost == Money.create('ARS', '2500')


def test_pharmacy_cannot_change_another_pharmacy_quote():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    other_user = _user('otra-farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)

    _assert_raises(
        QuoteRequest.DoesNotExist,
        lambda: submit_quote(other_user.id, conversation.id, _params()),
    )


def test_pharmacy_cannot_edit_or_withdraw_an_accepted_quote():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    _, conversation = open_conversation(customer, pharmacy_user)
    submit_quote(pharmacy_user.id, conversation.id, _params())
    quote_request = conversation.quote_request
    quote_request.status = QuoteRequestStatus.ACCEPTED
    quote_request.save(update_fields=['status'])

    _assert_raises(
        QuoteCannotBeEditedError,
        lambda: submit_quote(pharmacy_user.id, conversation.id, _params()),
    )
    _assert_raises(
        QuoteCannotBeWithdrawnError,
        lambda: withdraw_quote(pharmacy_user.id, conversation.id),
    )
