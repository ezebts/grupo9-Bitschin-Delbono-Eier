from django.db import transaction

from chats.models import Message
from orders.models import QuoteRequest


@transaction.atomic
def withdraw_quote(user_id, conversation_id):
    """Withdraws a quote that is still awaiting the client's reply."""

    quote_request = (
        QuoteRequest.objects.select_for_update()
        .select_related('conversation')
        .get(
            conversation__pk=conversation_id,
            pharmacy__accounts__user_id=user_id,
        )
    )
    quote_request.withdraw_quote()
    quote_request.save(update_fields=['status'])

    conversation = quote_request.conversation
    Message.objects.create(
        conversation=conversation,
        body='La farmacia retiró el presupuesto.',
        sender=Message.Sender.SYSTEM,
    )
    conversation.save(update_fields=['updated_at'])

    return quote_request
