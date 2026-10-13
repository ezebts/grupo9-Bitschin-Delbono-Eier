from django.db import transaction

from chats.models import Conversation
from orders.models import QuoteRequest


@transaction.atomic
def start_conversation(user_id, quote_request_id) -> int:
    """Opens the conversation that belongs to one quote request."""

    quote_request = QuoteRequest.objects.select_related('order').get(
        pk=quote_request_id,
        order__client_account__user_id=user_id,
    )

    try:
        return quote_request.conversation.id
    except Conversation.DoesNotExist:
        conversation = Conversation.objects.create(
            quote_request=quote_request,
            title=quote_request.order.formula[:200],
        )

        return conversation.id
