from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.db.models import F, OuterRef, Subquery

from accounts.models import PreparationTag, User
from chats.models import Conversation, Message
from orders.models import (
    DeliveryPreference,
    FulfillmentStatus,
    Order,
    OrderProgress,
    QuoteRequestStatus,
    Urgency,
)

QUOTE_CARD_SYSTEM_MESSAGES = (
    'La farmacia envió un presupuesto.',
    'La farmacia actualizó el presupuesto.',
)

WITHDRAWN_QUOTE_SYSTEM_MESSAGE = 'La farmacia retiró el presupuesto.'

PREPARATION_SYSTEM_MESSAGE = 'La farmacia marcó el pedido como «En preparación».'


@dataclass(frozen=True)
class ChatMessage:
    body: str
    created_at: datetime
    is_customer: bool
    is_pharmacy: bool
    is_system: bool
    follow_with_quote_card: bool = False
    follow_with_withdrawn_notice: bool = False
    estimated_at: date | None = None


@dataclass(frozen=True)
class ListedConversation:
    id: int
    title: str
    pharmacy_name: str
    waiting_for_pharmacy: bool
    quote_status: str
    quote_status_label: str
    quote_currency: str
    delivery_cost_currency: str
    quote_price: Decimal | None
    preparation_time: str
    updated_at: datetime
    last_message: ChatMessage | None


@dataclass(frozen=True)
class OpenConversation:
    id: int
    title: str
    pharmacy_name: str
    address: str
    hours: str
    quote_status: str
    quote_status_label: str
    quote_currency: str
    delivery_cost_currency: str
    quote_price: Decimal | None
    preparation_time: str
    delivery_preference_label: str
    delivery_cost: Decimal
    valid_until: date | None
    quoted_at: datetime | None
    quote_card_at_end: bool
    delivered: bool
    messages: tuple[ChatMessage, ...]


@dataclass(frozen=True)
class CustomerInbox:
    conversations: tuple[ListedConversation, ...]
    code: str
    formula: str
    progress_label: str
    preparation_label: str
    presentation: str
    urgency_label: str
    delivery_label: str
    created_at: datetime
    quotes_received: int
    quotes_total: int
    prescription_name: str
    prescription_url: str
    can_change_prescription: bool


def get_customer_inbox(user_id, order_id) -> CustomerInbox:
    """Lists the conversations of one order that belong to a customer."""

    order = (
        Order.objects.filter(client_account__user_id=user_id)
        .with_progress()
        .with_quote_counts()
        .get(pk=order_id)
    )

    found = (
        Conversation.objects.for_customer(user_id)
        .for_order(order_id)
        .select_related('quote_request__pharmacy')
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

    listed = []
    for conversation in found:
        last_message = None
        last = last_messages.get(conversation.pk)

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
                waiting_for_pharmacy=(last is None or last.is_customer),
                quote_status=conversation.quote_request.status,
                quote_status_label=QuoteRequestStatus(
                    conversation.quote_request.status
                ).label,
                quote_currency=(
                    conversation.quote_request.price.currency.value
                    if conversation.quote_request.price
                    else ''
                ),
                delivery_cost_currency=(
                    conversation.quote_request.delivery_cost.currency.value
                ),
                quote_price=(
                    conversation.quote_request.price.amount
                    if conversation.quote_request.price
                    else None
                ),
                preparation_time=conversation.quote_request.preparation_time,
                updated_at=conversation.updated_at,
                last_message=last_message,
            )
        )

    return CustomerInbox(
        conversations=tuple(listed),
        code=order.code,
        formula=order.formula,
        progress_label=OrderProgress(order.progress_code).label,
        preparation_label=PreparationTag(order.preparation_tag).label,
        presentation=order.presentation,
        urgency_label=Urgency(order.urgency).label,
        delivery_label=' · '.join(
            DeliveryPreference(preference).label
            for preference in order.delivery_preferences
        ),
        created_at=order.created_at,
        quotes_received=order.quotes_received,
        quotes_total=order.quotes_total,
        prescription_name=(
            Path(order.prescription.name).name if order.prescription else ''
        ),
        prescription_url=order.prescription.url if order.prescription else '',
        can_change_prescription=order.can_change_prescription,
    )


def get_customer_conversation(user_id, order_id, conversation_id) -> OpenConversation:
    """Reads one conversation that belongs to a customer and an order."""

    user = User.objects.get(pk=user_id)

    conversation = (
        Conversation.objects.with_messages()
        .select_related('quote_request__pharmacy', 'quote_request__order')
        .for_customer(user_id)
        .for_order(order_id)
        .get(pk=conversation_id)
    )

    pharmacy = conversation.quote_request.pharmacy
    address = pharmacy.location.format() if pharmacy.location else ''

    moment = datetime.now(user.timezone)

    hours = pharmacy.opening_hours.format(moment) if pharmacy.opening_hours else ''
    quote_request = conversation.quote_request
    preparation = quote_request.order.status_events.filter(
        status=FulfillmentStatus.IN_PREPARATION,
    ).first()

    messages = []
    quote_card_after = None
    withdrawn_notice_after = None
    for message in conversation.messages.all():
        messages.append(
            ChatMessage(
                body=message.body,
                created_at=message.created_at,
                is_customer=message.is_customer,
                is_pharmacy=message.is_pharmacy,
                is_system=message.is_system,
                estimated_at=(
                    preparation.estimated_at
                    if preparation and message.body == PREPARATION_SYSTEM_MESSAGE
                    else None
                ),
            ),
        )
        if message.body in QUOTE_CARD_SYSTEM_MESSAGES:
            quote_card_after = len(messages) - 1
        if message.body == WITHDRAWN_QUOTE_SYSTEM_MESSAGE:
            withdrawn_notice_after = len(messages) - 1

    if (
        quote_card_after is not None
        and quote_request.status
        in (QuoteRequestStatus.QUOTED, QuoteRequestStatus.ACCEPTED)
        and quote_request.price is not None
    ):
        messages[quote_card_after] = replace(
            messages[quote_card_after],
            follow_with_quote_card=True,
        )

    if (
        withdrawn_notice_after is not None
        and quote_request.status == QuoteRequestStatus.WITHDRAWN
    ):
        messages[withdrawn_notice_after] = replace(
            messages[withdrawn_notice_after],
            follow_with_withdrawn_notice=True,
        )

    quote_card_at_end = (
        quote_card_after is None
        and quote_request.price is not None
        and quote_request.status
        in (QuoteRequestStatus.QUOTED, QuoteRequestStatus.ACCEPTED)
    )

    return OpenConversation(
        id=conversation.pk,
        title=conversation.title,
        pharmacy_name=pharmacy.trade_name,
        address=address,
        hours=hours,
        quote_status=quote_request.status,
        quote_status_label=QuoteRequestStatus(quote_request.status).label,
        quote_currency=(
            quote_request.price.currency.value if quote_request.price else ''
        ),
        delivery_cost_currency=quote_request.delivery_cost.currency.value,
        quote_price=quote_request.price.amount if quote_request.price else None,
        preparation_time=quote_request.preparation_time,
        delivery_preference_label=(
            ' o '.join(
                DeliveryPreference(preference).label.lower()
                for preference in quote_request.delivery_preferences
            )
        ),
        delivery_cost=quote_request.delivery_cost.amount,
        valid_until=quote_request.valid_until,
        quoted_at=quote_request.quoted_at,
        quote_card_at_end=quote_card_at_end,
        delivered=(
            quote_request.status == QuoteRequestStatus.ACCEPTED
            and quote_request.order.fulfillment_status == FulfillmentStatus.DELIVERED
        ),
        messages=tuple(messages),
    )
