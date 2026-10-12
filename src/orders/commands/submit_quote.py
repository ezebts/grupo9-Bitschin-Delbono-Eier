from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction

from accounts.models import User
from orders.exceptions import (
    ExpiredQuoteDateError,
    InvalidDeliveryCostError,
    InvalidQuotePriceError,
    QuoteCannotBeEditedError,
)
from orders.models import DeliveryPreference, QuoteRequest, QuoteRequestStatus
from shared.values import Money


@dataclass(frozen=True)
class SubmitQuoteParams:
    price: Money
    preparation_time: str
    delivery_preferences: tuple[str, ...]
    delivery_cost: Money
    valid_until: date


@transaction.atomic
def submit_quote(user_id, conversation_id, params: SubmitQuoteParams):
    """Submits a quote or edits one that is still awaiting the client's reply."""

    quote_request = (
        QuoteRequest.objects.select_for_update()
        .select_related('conversation', 'order')
        .get(
            conversation__pk=conversation_id,
            pharmacy__accounts__user_id=user_id,
        )
    )

    if params.price.amount <= 0:
        raise InvalidQuotePriceError

    if (
        DeliveryPreference.HOME_DELIVERY in params.delivery_preferences
        and params.delivery_cost.amount <= 0
    ):
        raise InvalidDeliveryCostError

    user = User.objects.only('_timezone').get(pk=user_id)
    if params.valid_until < datetime.now(user.timezone).date():
        raise ExpiredQuoteDateError

    is_update = quote_request.status == QuoteRequestStatus.QUOTED

    if is_update:
        quote_request.update_quote()
        system_message = 'La farmacia actualizó el presupuesto.'
    elif quote_request.status == QuoteRequestStatus.WAITING:
        quote_request.submit_quote()
        system_message = 'La farmacia envió un presupuesto.'
    else:
        raise QuoteCannotBeEditedError

    quote_request.set_quote_terms(
        price=params.price,
        preparation_time=params.preparation_time,
        delivery_preferences=params.delivery_preferences,
        delivery_cost=params.delivery_cost,
        valid_until=params.valid_until,
    )

    quote_request.save(
        update_fields=(
            'status',
            '_price',
            'preparation_time',
            '_delivery_preferences',
            '_delivery_cost',
            'valid_until',
            'quoted_at',
        ),
    )

    message = quote_request.conversation.send_system_message(system_message)
    message.save()

    quote_request.conversation.save(update_fields=['updated_at'])

    return quote_request
