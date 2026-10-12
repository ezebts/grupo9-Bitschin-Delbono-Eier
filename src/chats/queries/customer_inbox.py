from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.db.models import F, OuterRef, Subquery

from accounts.models import PreparationTag, User
from chats.models import Conversation, Message
from orders.models import DeliveryPreference, Order, OrderProgress, Urgency


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
    pharmacy_name: str
    waiting_for_pharmacy: bool
    updated_at: datetime
    last_message: ChatMessage | None


@dataclass(frozen=True)
class OpenConversation:
    id: int
    title: str
    pharmacy_name: str
    address: str
    hours: str
    messages: tuple[ChatMessage, ...]


@dataclass(frozen=True)
class CustomerInbox:
    conversations: tuple[ListedConversation, ...]
    code: str
    progress_label: str
    preparation_label: str
    presentation: str
    urgency_label: str
    delivery_label: str
    created_at: datetime
    prescription_name: str
    prescription_url: str


def get_customer_inbox(user_id, order_id) -> CustomerInbox:
    """Lists the conversations of one order that belong to a customer."""

    order = (
        Order.objects.filter(client_account__user_id=user_id)
        .with_progress()
        .get(pk=order_id)
    )

    found = (
        Conversation.objects.for_customer(user_id)
        .for_order(order_id)
        .annotate(pharmacy_name=F('quote_request__pharmacy__trade_name'))
    )

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
                pharmacy_name=conversation.pharmacy_name,
                waiting_for_pharmacy=last_user is None or last_user.is_customer,
                updated_at=conversation.updated_at,
                last_message=last_message,
            )
        )

    return CustomerInbox(
        conversations=tuple(listed),
        code=order.code,
        progress_label=OrderProgress(order.progress_code).label,
        preparation_label=PreparationTag(order.preparation_tag).label,
        presentation=order.presentation,
        urgency_label=Urgency(order.urgency).label,
        delivery_label=' · '.join(
            DeliveryPreference(preference).label
            for preference in order.delivery_preferences
        ),
        created_at=order.created_at,
        prescription_name=(
            Path(order.prescription.name).name if order.prescription else ''
        ),
        prescription_url=order.prescription.url if order.prescription else '',
    )


def get_customer_conversation(user_id, order_id, conversation_id) -> OpenConversation:
    """Reads one conversation that belongs to a customer and an order."""

    user = User.objects.get(pk=user_id)

    conversation = (
        Conversation.objects.with_messages()
        .select_related('quote_request__pharmacy')
        .for_customer(user_id)
        .for_order(order_id)
        .get(pk=conversation_id)
    )

    pharmacy = conversation.quote_request.pharmacy
    address = pharmacy.location.format() if pharmacy.location else ''

    moment = datetime.now(user.timezone)

    hours = pharmacy.opening_hours.format(moment) if pharmacy.opening_hours else ''

    return OpenConversation(
        id=conversation.pk,
        title=conversation.title,
        pharmacy_name=pharmacy.trade_name,
        address=address,
        hours=hours,
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
