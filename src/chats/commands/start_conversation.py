from django.db import transaction

from accounts.models import PharmacyAccount
from chats.models import Conversation
from orders.models import QuoteRequest
from shared.secured_conversations import generate_conversation_keypair


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
        server_key = {}
        pharmacy_has_account = PharmacyAccount.objects.filter(
            pharmacy_id=quote_request.pharmacy_id,
        ).exists()
        if not pharmacy_has_account:
            public_key, fingerprint, private_key = generate_conversation_keypair()
            server_key = {
                'server_public_key': public_key,
                'server_key_fingerprint': fingerprint,
                'server_private_key': private_key,
            }

        conversation = Conversation.objects.create(
            quote_request=quote_request,
            **server_key,
        )

        return conversation.id
