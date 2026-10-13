from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction

from accounts.models import User
from orders.models import QuoteRequest, QuoteRequestStatus


@dataclass(frozen=True)
class AdvanceOrderParams:
    estimated_at: date | None


@transaction.atomic
def advance_order(user_id, conversation_id, params: AdvanceOrderParams):
    """Moves an accepted order to its next status and lets the client know."""

    quote_request = (
        QuoteRequest.objects.select_for_update()
        .select_related('conversation', 'order')
        .get(
            conversation__pk=conversation_id,
            pharmacy__accounts__user_id=user_id,
            status=QuoteRequestStatus.ACCEPTED,
        )
    )

    user = User.objects.only('_timezone').get(pk=user_id)
    order = quote_request.order
    event = order.advance_fulfillment(
        params.estimated_at,
        datetime.now(user.timezone).date(),
    )
    event.save()

    status_label = order.fulfillment_label(event.status)

    conversation = quote_request.conversation
    message = conversation.send_system_message(
        f'La farmacia marcó el pedido como «{status_label}».',
    )
    message.save()
    conversation.save(update_fields=['updated_at'])

    return event
