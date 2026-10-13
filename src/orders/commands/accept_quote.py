from datetime import datetime

from django.db import transaction

from accounts.models import User
from orders.models import QuoteRequest, QuoteRequestStatus


@transaction.atomic
def accept_quote(user_id, conversation_id):
    """Accepts a quote and lets the other pharmacies of the order know."""

    quote_request = (
        QuoteRequest.objects.select_for_update()
        .select_related('conversation')
        .get(
            conversation__pk=conversation_id,
            order__client_account__user_id=user_id,
        )
    )

    user = User.objects.only('_timezone').get(pk=user_id)
    quote_request.accept_quote(datetime.now(user.timezone).date())
    quote_request.save(update_fields=['status'])

    conversation = quote_request.conversation
    message = conversation.send_system_message('El cliente aceptó el presupuesto.')
    message.save()
    conversation.save(update_fields=['updated_at'])

    others = (
        QuoteRequest.objects.select_for_update(of=('self',))
        .select_related('conversation')
        .filter(
            order_id=quote_request.order_id,
            status__in=(QuoteRequestStatus.WAITING, QuoteRequestStatus.QUOTED),
        )
    )

    for other in others:
        other.mark_not_chosen()
        other.save(update_fields=['status'])

        message = other.conversation.send_system_message(
            'El cliente eligió otra farmacia.',
        )
        message.save()
        other.conversation.save(update_fields=['updated_at'])

    return quote_request
