from django.core.files import File
from django.db import transaction

from orders.exceptions import (
    PrescriptionAlreadyAttachedError,
    PrescriptionCannotChangeError,
)
from orders.models import Order


def _open_order(user_id, order_id):
    order = Order.objects.select_for_update().get(
        pk=order_id,
        client_account__user_id=user_id,
    )
    if not order.can_change_prescription:
        raise PrescriptionCannotChangeError
    return order


@transaction.atomic
def attach_order_prescription(user_id, order_id, prescription: File):
    """Stores the client's prescription while no quote is accepted."""

    order = _open_order(user_id, order_id)
    if order.prescription:
        raise PrescriptionAlreadyAttachedError
    prescription.seek(0)
    order.attach_prescription(prescription)
    order.save(update_fields=['prescription'])
    return order


@transaction.atomic
def remove_order_prescription(user_id, order_id):
    """Removes the client's prescription while no quote is accepted."""

    order = _open_order(user_id, order_id)
    if not order.prescription:
        return order
    order.remove_prescription()
    order.save(update_fields=['prescription'])
    return order
