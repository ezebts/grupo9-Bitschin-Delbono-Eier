from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db.models import F, OuterRef, Subquery

from accounts.models import Pharmacy, PreparationTag
from accounts.models.pharmacies import GEO_WGS84_LAT_LONG
from chats.models import Conversation, Message
from chats.queries.customer_inbox import (
    PREPARATION_SYSTEM_MESSAGE,
    QUOTE_CARD_SYSTEM_MESSAGES,
    WITHDRAWN_QUOTE_SYSTEM_MESSAGE,
)
from orders.models import (
    DeliveryPreference,
    FulfillmentStatus,
    QuoteRequestStatus,
    StatusEvent,
    Urgency,
)
from shared.files import file_size_label


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
class FulfillmentStep:
    label: str
    reached_at: datetime | None
    estimated_at: date | None
    done: bool
    current: bool


@dataclass(frozen=True)
class ListedConversation:
    id: int
    title: str
    customer_name: str
    quote_status: str
    fulfillment_label: str
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
    quote_currency: str
    delivery_cost_currency: str
    quote_price: Decimal | None
    preparation_time: str
    delivery_preference_label: str
    delivery_preferences: tuple[str, ...]
    delivery_cost: Decimal
    valid_until: date | None
    quoted_at: datetime | None
    delivery_options: tuple[str, ...]
    order_code: str
    order_created_at: datetime
    preparation_label: str
    presentation: str
    urgency_label: str
    delivery_label: str
    primary_delivery_label: str
    customer_zone_label: str
    order_note: str
    prescription_name: str
    prescription_size_label: str
    prescription_url: str
    quote_card_at_end: bool
    messages: tuple[ChatMessage, ...]
    fulfillment_label: str
    fulfillment_steps: tuple[FulfillmentStep, ...]
    next_fulfillment_label: str
    asks_estimated_date: bool


@dataclass(frozen=True)
class PharmacyInbox:
    conversations: tuple[ListedConversation, ...]
    waiting_count: int
    quoted_count: int
    accepted_count: int


def _customer_zone_label(order, pharmacy) -> str:
    client_location = order.client_account.location
    if client_location is None:
        return ''
    locality = (client_location.locality or '').strip()
    if not locality:
        return ''

    client_coordinates = client_location.coordinates
    if client_coordinates is None or pharmacy.coordinates is None:
        return locality

    client_point = Point(
        client_coordinates.longitude,
        client_coordinates.latitude,
        srid=GEO_WGS84_LAT_LONG,
    )
    distance = (
        Pharmacy.objects.filter(pk=pharmacy.pk)
        .annotate(distance=Distance('coordinates', client_point))
        .values_list('distance', flat=True)
        .first()
    )
    if distance is None:
        return locality

    km_label = f'{distance.km:.1f}'.replace('.', ',')
    return f'{locality} · aprox. {km_label} km en línea recta'


def get_pharmacy_inbox(
    user_id,
    search='',
    *,
    quote_filter: QuoteRequestStatus = QuoteRequestStatus.WAITING,
) -> PharmacyInbox:
    """Lists the conversations that belong to a pharmacy."""

    found = Conversation.objects.for_pharmacy(user_id).select_related(
        'quote_request__order__client_account__user',
    )

    if search:
        found = found.search(search)

    found = found.filter(quote_request__status=quote_filter)

    latest_status = StatusEvent.objects.filter(
        order=OuterRef('quote_request__order'),
    ).order_by('-created_at', '-pk')

    found = found.annotate(
        fulfillment_status=Subquery(latest_status.values('status')[:1]),
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

        order = conversation.quote_request.order
        user = order.client_account.user
        customer_name = f'{user.first_name} {user.last_name}'.strip()

        listed.append(
            ListedConversation(
                id=conversation.pk,
                title=conversation.title,
                customer_name=customer_name,
                quote_status=conversation.quote_request.status,
                fulfillment_label=(
                    order.fulfillment_label(conversation.fulfillment_status)
                    if conversation.quote_request.status == QuoteRequestStatus.ACCEPTED
                    and conversation.fulfillment_status
                    else ''
                ),
                waiting_for_pharmacy=(last is None or last.is_customer),
                updated_at=conversation.updated_at,
                last_message=last_message,
            )
        )

    owned = Conversation.objects.for_pharmacy(user_id)

    return PharmacyInbox(
        conversations=tuple(listed),
        waiting_count=owned.filter(
            quote_request__status=QuoteRequestStatus.WAITING,
        ).count(),
        quoted_count=owned.filter(
            quote_request__status=QuoteRequestStatus.QUOTED,
        ).count(),
        accepted_count=owned.filter(
            quote_request__status=QuoteRequestStatus.ACCEPTED,
        ).count(),
    )


def get_conversation(user_id, conversation_id) -> OpenConversation:
    """Reads one conversation that belongs to a pharmacy."""

    customer = 'quote_request__order__client_account__user'

    conversation = (
        Conversation.objects.with_messages()
        .for_pharmacy(user_id)
        .select_related(
            'quote_request__order__client_account',
            'quote_request__pharmacy',
        )
        .prefetch_related('quote_request__order__status_events')
        .annotate(
            customer_first_name=F(f'{customer}__first_name'),
            customer_last_name=F(f'{customer}__last_name'),
        )
        .get(pk=conversation_id)
    )

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

    latest_conversation_sender = (
        conversation.messages.order_by('-created_at', '-pk')
        .values_list('sender', flat=True)
        .first()
    )

    customer_name = (
        f'{conversation.customer_first_name} {conversation.customer_last_name}'
    ).strip()
    order = quote_request.order
    pharmacy = quote_request.pharmacy
    accepted = quote_request.status == QuoteRequestStatus.ACCEPTED
    next_status = order.next_fulfillment_status if accepted else None

    return OpenConversation(
        id=conversation.pk,
        title=conversation.title,
        customer_name=customer_name,
        waiting_for_pharmacy=latest_conversation_sender
        in {None, Message.Sender.CUSTOMER},
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
        delivery_preferences=quote_request.delivery_preferences,
        delivery_cost=quote_request.delivery_cost.amount,
        valid_until=quote_request.valid_until,
        quoted_at=quote_request.quoted_at,
        delivery_options=tuple(order.delivery_preferences),
        order_code=order.code,
        order_created_at=order.created_at,
        preparation_label=PreparationTag(order.preparation_tag).label,
        presentation=order.presentation,
        urgency_label=Urgency(order.urgency).label,
        delivery_label=' · '.join(
            DeliveryPreference(preference).label
            for preference in order.delivery_preferences
        ),
        primary_delivery_label=(
            DeliveryPreference(order.delivery_preferences[0]).label
            if order.delivery_preferences
            else ''
        ),
        customer_zone_label=_customer_zone_label(order, pharmacy),
        order_note=order.note,
        prescription_name=(
            Path(order.prescription.name).name if order.prescription else ''
        ),
        prescription_size_label=file_size_label(order.prescription),
        prescription_url=order.prescription.url if order.prescription else '',
        quote_card_at_end=quote_card_at_end,
        messages=tuple(messages),
        fulfillment_label=(
            order.fulfillment_label(order.fulfillment_status) if accepted else ''
        ),
        fulfillment_steps=_fulfillment_steps(order) if accepted else (),
        next_fulfillment_label=(
            order.fulfillment_label(next_status) if accepted and next_status else ''
        ),
        asks_estimated_date=next_status == FulfillmentStatus.IN_PREPARATION,
    )


def _fulfillment_steps(order) -> tuple[FulfillmentStep, ...]:
    events = {event.status: event for event in order.status_events.all()}
    statuses = list(FulfillmentStatus)
    current = order.fulfillment_status
    current_index = statuses.index(current) if current else -1

    return tuple(
        FulfillmentStep(
            label=order.fulfillment_label(status),
            reached_at=events[status].created_at if status in events else None,
            estimated_at=events[status].estimated_at if status in events else None,
            done=index < current_index,
            current=index == current_index,
        )
        for index, status in enumerate(statuses)
    )
