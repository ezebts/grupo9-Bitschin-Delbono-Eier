from django.db import transaction

from accounts.models import User
from chats.models import Conversation


@transaction.atomic
def send_message(user_id, conversation_id, text):
    """Sends a message in a conversation the user can write in."""

    user = User.objects.get(pk=user_id)

    conversations = Conversation.objects.all()

    if user.is_customer:
        conversations = conversations.for_customer(user_id)
    elif user.is_pharmacy:
        conversations = conversations.for_pharmacy(user_id)

    conversation = conversations.get(pk=conversation_id)

    message = conversation.send_message(
        user.id,
        user.get_full_name() or user.email,
        text,
    )

    message.save()
    conversation.save(update_fields=['updated_at'])
