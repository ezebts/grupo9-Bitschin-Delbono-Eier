from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Q

from orders.models import Order, OrderProgress


@dataclass(frozen=True)
class ListedOrder:
    id: int
    formula: str
    presentation: str
    code: str
    created_at: datetime
    quotes_received: int
    quotes_total: int
    status: str
    status_label: str


@dataclass(frozen=True)
class ClientOrders:
    orders: tuple[ListedOrder, ...]
    total: int
    waiting: int
    quoted: int
    in_progress: int
    finished: int


def list_client_orders(user_id, status='') -> ClientOrders:
    """Lists a client's orders, optionally filtered by the screen tabs."""

    orders = Order.objects.filter(
        client_account__user_id=user_id,
    ).with_progress()

    counts = orders.aggregate(
        total=Count('pk'),
        waiting=Count('pk', filter=Q(progress_code=OrderProgress.WAITING)),
        quoted=Count('pk', filter=Q(progress_code=OrderProgress.QUOTED)),
        in_progress=Count('pk', filter=Q(progress_code=OrderProgress.IN_PROGRESS)),
        finished=Count('pk', filter=Q(progress_code=OrderProgress.FINISHED)),
    )

    visible = orders.with_quote_counts()
    if status in OrderProgress.values:
        visible = visible.filter(progress_code=status)

    orders = []
    for order in visible:
        orders.append(
            ListedOrder(
                id=order.pk,
                formula=order.formula,
                presentation=order.presentation,
                code=order.code,
                created_at=order.created_at,
                quotes_received=order.quotes_received,
                quotes_total=order.quotes_total,
                status=OrderProgress(order.progress_code),
                status_label=OrderProgress(order.progress_code).label,
            )
        )

    return ClientOrders(
        orders=tuple(orders),
        total=counts['total'],
        waiting=counts['waiting'],
        quoted=counts['quoted'],
        in_progress=counts['in_progress'],
        finished=counts['finished'],
    )
