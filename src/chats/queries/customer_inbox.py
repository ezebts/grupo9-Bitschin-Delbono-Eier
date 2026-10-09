from dataclasses import dataclass
from datetime import datetime

from django.db.models import OuterRef, Subquery

from chats.models import Conversation, Message


@dataclass(frozen=True)
class ChatMessage:
    body: str
    created_at: datetime
    is_customer: bool
    is_pharmacy: bool
    is_system: bool


@dataclass(frozen=True)
class ListedConversation:
    id: int
    title: str
    waiting_for_pharmacy: bool
    updated_at: datetime
    last_message: ChatMessage | None


@dataclass(frozen=True)
class OpenConversation:
    id: int
    title: str
    messages: tuple[ChatMessage, ...]


@dataclass(frozen=True)
class CustomerInbox:
    conversations: tuple[ListedConversation, ...]


def get_customer_inbox(user_id) -> CustomerInbox:
    """Lists the conversations that belong to a customer."""

    found = Conversation.objects.for_customer(user_id)

    conversation_ids = found.values('pk')

    latest = Message.objects.filter(
        conversation_id=OuterRef('conversation_id'),
    ).order_by('-created_at', '-pk')

    last_messages = {
        message.conversation_id: message
        for message in Message.objects.filter(
            conversation_id__in=conversation_ids,
            pk=Subquery(latest.values('pk')[:1]),
        )
    }

    last_user_messages = {
        message.conversation_id: message
        for message in Message.objects.filter(
            conversation_id__in=conversation_ids,
            pk=Subquery(
                latest.exclude(sender=Message.Sender.SYSTEM).values('pk')[:1],
            ),
        )
    }

    listed = []
    for conversation in found:
        last_message = None
        last = last_messages.get(conversation.pk)
        last_user = last_user_messages.get(conversation.pk)

        if last is not None:
            last_message = ChatMessage(
                body=last.body,
                created_at=last.created_at,
                is_customer=last.is_customer,
                is_pharmacy=last.is_pharmacy,
                is_system=last.is_system,
            )

        listed.append(
            ListedConversation(
                id=conversation.pk,
                title=conversation.title,
                waiting_for_pharmacy=last_user is None or last_user.is_customer,
                updated_at=conversation.updated_at,
                last_message=last_message,
            )
        )

    return CustomerInbox(conversations=tuple(listed))


def get_customer_conversation(user_id, conversation_id) -> OpenConversation:
    """Reads one conversation that belongs to a customer."""

    conversation = (
        Conversation.objects.with_messages()
        .for_customer(user_id)
        .get(pk=conversation_id)
    )

    return OpenConversation(
        id=conversation.pk,
        title=conversation.title,
        messages=tuple(
            ChatMessage(
                body=message.body,
                created_at=message.created_at,
                is_customer=message.is_customer,
                is_pharmacy=message.is_pharmacy,
                is_system=message.is_system,
            )
            for message in conversation.messages.all()
        ),
    )
