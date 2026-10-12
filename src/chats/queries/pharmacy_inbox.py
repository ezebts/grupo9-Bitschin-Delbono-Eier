from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db.models import F, OuterRef, Subquery

from chats.models import Conversation, Message
from orders.models import DeliveryPreference, QuoteRequestStatus


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
    customer_name: str
    waiting_for_pharmacy: bool
    quote_status: str
    quote_status_label: str
    quote_price: Decimal | None
    preparation_time: str
    delivery_preference_label: str
    delivery_preferences: tuple[str, ...]
    delivery_cost: Decimal
    valid_until: date | None
    quoted_at: datetime | None
    delivery_options: tuple[str, ...]
    messages: tuple[ChatMessage, ...]


@dataclass(frozen=True)
class PharmacyInbox:
    conversations: tuple[ListedConversation, ...]
    open_count: int
    pending_count: int


def get_pharmacy_inbox(user_id, search='', *, unread_only=False) -> PharmacyInbox:
    """Lists the conversations that belong to a pharmacy."""

    found = Conversation.objects.for_pharmacy(user_id)

    if search:
        found = found.search(search)

    if unread_only:
        found = found.pending()

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

    listed = []
    for conversation in found:
        last = last_messages.get(conversation.pk)
        last_message = None

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
                waiting_for_pharmacy=(last is None or last.is_customer),
                updated_at=conversation.updated_at,
                last_message=last_message,
            )
        )

    owned = Conversation.objects.for_pharmacy(user_id)

    return PharmacyInbox(
        conversations=tuple(listed),
        open_count=owned.count(),
        pending_count=owned.pending().count(),
    )


def get_conversation(user_id, conversation_id) -> OpenConversation:
    """Reads one conversation that belongs to a pharmacy."""

    customer = 'quote_request__order__client_account__user'

    conversation = (
        Conversation.objects.with_messages()
        .for_pharmacy(user_id)
        .select_related(
            'quote_request__order',
            'quote_request__pharmacy',
        )
        .annotate(
            customer_first_name=F(f'{customer}__first_name'),
            customer_last_name=F(f'{customer}__last_name'),
        )
        .get(pk=conversation_id)
    )

    messages = tuple(
        ChatMessage(
            body=message.body,
            created_at=message.created_at,
            is_customer=message.is_customer,
            is_pharmacy=message.is_pharmacy,
            is_system=message.is_system,
        )
        for message in conversation.messages.all()
    )

    latest_conversation_sender = (
        conversation.messages.order_by('-created_at', '-pk')
        .values_list('sender', flat=True)
        .first()
    )

    customer_name = (
        f'{conversation.customer_first_name} {conversation.customer_last_name}'
    ).strip()
    quote_request = conversation.quote_request

    return OpenConversation(
        id=conversation.pk,
        title=conversation.title,
        customer_name=customer_name,
        waiting_for_pharmacy=latest_conversation_sender
        in {None, Message.Sender.CUSTOMER},
        quote_status=quote_request.status,
        quote_status_label=QuoteRequestStatus(quote_request.status).label,
        quote_price=quote_request.price,
        preparation_time=quote_request.preparation_time,
        delivery_preference_label=(
            ' o '.join(
                DeliveryPreference(preference).label.lower()
                for preference in quote_request.delivery_preferences
            )
        ),
        delivery_preferences=quote_request.delivery_preferences,
        delivery_cost=quote_request.delivery_cost,
        valid_until=quote_request.valid_until,
        quoted_at=quote_request.quoted_at,
        delivery_options=tuple(quote_request.order.delivery_preferences),
        messages=messages,
    )
