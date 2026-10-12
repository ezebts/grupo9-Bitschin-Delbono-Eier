from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from chats.models import Message
from orders.exceptions import (
    ExpiredQuoteDateError,
    InvalidQuoteAmountError,
    MissingPreparationTimeError,
    PickupDeliveryCostError,
    QuoteCannotBeEditedError,
    QuoteDeliveryNotRequestedError,
)
from orders.models import DeliveryPreference, QuoteRequest, QuoteRequestStatus


@dataclass(frozen=True)
class QuoteTerms:
    price: Decimal
    preparation_time: str
    delivery_preferences: tuple[str, ...]
    delivery_cost: Decimal
    valid_until: date


@transaction.atomic
def save_quote(user_id, conversation_id, terms: QuoteTerms):
    """Submits a quote or edits one that is still awaiting the client's reply."""

    quote_request = (
        QuoteRequest.objects.select_for_update()
        .select_related('conversation', 'order')
        .get(
            conversation__pk=conversation_id,
            pharmacy__accounts__user_id=user_id,
        )
    )
    if not terms.delivery_preferences or not set(terms.delivery_preferences).issubset(
        quote_request.order.delivery_preferences,
    ):
        raise QuoteDeliveryNotRequestedError
    if terms.price <= 0 or terms.delivery_cost < 0:
        raise InvalidQuoteAmountError
    if (
        DeliveryPreference.HOME_DELIVERY not in terms.delivery_preferences
        and terms.delivery_cost != 0
    ):
        raise PickupDeliveryCostError
    if not terms.preparation_time.strip():
        raise MissingPreparationTimeError
    if terms.valid_until < timezone.localdate():
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
        price=terms.price,
        preparation_time=terms.preparation_time,
        delivery_preferences=terms.delivery_preferences,
        delivery_cost=terms.delivery_cost,
        valid_until=terms.valid_until,
    )
    quote_request.save(
        update_fields=(
            'status',
            'price',
            'preparation_time',
            '_delivery_preferences',
            'delivery_cost',
            'valid_until',
            'quoted_at',
        ),
    )

    conversation = quote_request.conversation
    Message.objects.create(
        conversation=conversation,
        body=system_message,
        sender=Message.Sender.SYSTEM,
    )
    conversation.save(update_fields=['updated_at'])

    return quote_request
