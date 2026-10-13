from django.db import transaction

from orders.models import QuoteRequest


@transaction.atomic
def reject_quote(user_id, conversation_id):
    """Rejects a quote the client does not want."""

    quote_request = (
        QuoteRequest.objects.select_for_update()
        .select_related('conversation')
        .get(
            conversation__pk=conversation_id,
            order__client_account__user_id=user_id,
        )
    )
    quote_request.reject_quote()
    quote_request.save(update_fields=['status'])

    conversation = quote_request.conversation
    message = conversation.send_system_message('El cliente rechazó el presupuesto.')
    message.save()
    conversation.save(update_fields=['updated_at'])

    return quote_request
