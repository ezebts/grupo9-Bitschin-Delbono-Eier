from dataclasses import dataclass

from django.core.files import File
from django.db import transaction

from accounts.models import User
from orders.models import Order


@dataclass(frozen=True)
class CreateOrderParams:
    preparation_tag: str
    presentation: str
    formula: str
    urgency: str
    delivery_preferences: tuple[str, ...]
    note: str
    prescription: File | None = None


@transaction.atomic
def create_order(user_id, params: CreateOrderParams):
    """Creates one order for the client."""

    user = User.objects.select_related('client_account').get(pk=user_id)

    order = Order.create(
        user.client_account,
        params.formula,
        params.presentation,
        params.urgency,
        params.delivery_preferences,
        params.note,
        params.preparation_tag,
    )

    order.save()

    if params.prescription is not None:
        order.attach_prescription(params.prescription)
        order.save(update_fields=['prescription'])

    return order
