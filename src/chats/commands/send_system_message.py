from django.db import transaction

from chats.models import Conversation


@transaction.atomic
def send_system_message(conversation_id, text):
    """Sends a system notice in a conversation."""

    conversation = Conversation.objects.get(pk=conversation_id)
    message = conversation.send_system_message(text)

    message.save()
    conversation.save(update_fields=['updated_at'])
