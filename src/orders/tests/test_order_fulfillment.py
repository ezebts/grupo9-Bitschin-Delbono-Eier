from datetime import datetime, timedelta

import pytest

from accounts.models import Pharmacy, PharmacyAccount, User
from chats.queries.customer_inbox import (
    PREPARATION_SYSTEM_MESSAGE,
    get_customer_conversation,
)
from chats.tests.support import open_conversation
from orders.commands.accept_quote import accept_quote
from orders.commands.advance_order import AdvanceOrderParams, advance_order
from orders.commands.request_quote import request_quote
from orders.commands.submit_quote import submit_quote
from orders.exceptions import InvalidEstimatedDateError, OrderCannotAdvanceError
from orders.models import (
    DeliveryPreference,
    FulfillmentStatus,
    OrderProgress,
    QuoteRequest,
)
from orders.queries.client_orders import list_client_orders
from orders.tests.test_quote_management import _assert_raises, _params, _user

pytestmark = pytest.mark.django_db


def _accepted_order(delivery_preferences=(DeliveryPreference.PICKUP,)):
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    order, conversation = open_conversation(
        customer,
        pharmacy_user,
        delivery_preferences=delivery_preferences,
    )
    home_delivery = DeliveryPreference.HOME_DELIVERY in delivery_preferences
    delivery_cost = 2500 if home_delivery else 0
    submit_quote(
        pharmacy_user.id,
        conversation.id,
        _params(delivery_preferences=delivery_preferences, delivery_cost=delivery_cost),
    )
    accept_quote(customer.id, conversation.id)
    return customer, pharmacy_user, order, conversation


def _in_days(user, days):
    return AdvanceOrderParams(
        estimated_at=datetime.now(user.timezone).date() + timedelta(days=days),
    )


def test_pharmacy_moves_an_accepted_order_until_it_is_delivered():
    customer, pharmacy_user, order, conversation = _accepted_order()
    preparation = _in_days(pharmacy_user, 2)

    advance_order(pharmacy_user.id, conversation.id, preparation)
    chat = get_customer_conversation(customer.id, order.id, conversation.id)
    assert chat.messages[-1].body == PREPARATION_SYSTEM_MESSAGE
    assert chat.messages[-1].estimated_at == preparation.estimated_at

    advance_order(pharmacy_user.id, conversation.id, AdvanceOrderParams(None))
    advance_order(pharmacy_user.id, conversation.id, AdvanceOrderParams(None))

    assert list(order.status_events.values_list('status', flat=True)) == [
        FulfillmentStatus.ACCEPTED,
        FulfillmentStatus.IN_PREPARATION,
        FulfillmentStatus.READY_FOR_PICKUP,
        FulfillmentStatus.DELIVERED,
    ]
    assert (
        conversation.messages.last().body
        == 'La farmacia marcó el pedido como «Entregado».'
    )
    assert list_client_orders(customer.id, status=OrderProgress.FINISHED).finished == 1
    _assert_raises(
        OrderCannotAdvanceError,
        lambda: advance_order(
            pharmacy_user.id,
            conversation.id,
            AdvanceOrderParams(None),
        ),
    )


def test_preparation_needs_an_estimated_date_from_today():
    _customer, pharmacy_user, _order, conversation = _accepted_order()

    _assert_raises(
        InvalidEstimatedDateError,
        lambda: advance_order(
            pharmacy_user.id,
            conversation.id,
            AdvanceOrderParams(None),
        ),
    )
    _assert_raises(
        InvalidEstimatedDateError,
        lambda: advance_order(
            pharmacy_user.id,
            conversation.id,
            _in_days(pharmacy_user, -1),
        ),
    )


def test_only_the_chosen_pharmacy_can_move_the_order():
    customer = _user('cliente@example.com', User.Role.CUSTOMER)
    pharmacy_user = _user('farmacia@example.com', User.Role.PHARMACY)
    other_user = _user('otra-farmacia@example.com', User.Role.PHARMACY)
    order, conversation = open_conversation(customer, pharmacy_user)
    other_pharmacy = Pharmacy.objects.create(trade_name='Otra', visible=True)
    PharmacyAccount.objects.create(user=other_user, pharmacy=other_pharmacy)
    other_request = request_quote(order.id, other_pharmacy.id)
    submit_quote(pharmacy_user.id, conversation.id, _params())
    accept_quote(customer.id, conversation.id)

    _assert_raises(
        QuoteRequest.DoesNotExist,
        lambda: advance_order(
            other_user.id,
            other_request.conversation.id,
            _in_days(other_user, 1),
        ),
    )


def test_home_delivery_orders_are_on_the_way_instead_of_ready():
    _customer, pharmacy_user, _order, conversation = _accepted_order(
        delivery_preferences=(DeliveryPreference.HOME_DELIVERY,),
    )

    advance_order(pharmacy_user.id, conversation.id, _in_days(pharmacy_user, 1))
    advance_order(pharmacy_user.id, conversation.id, AdvanceOrderParams(None))

    assert (
        conversation.messages.last().body
        == 'La farmacia marcó el pedido como «En camino».'
    )
