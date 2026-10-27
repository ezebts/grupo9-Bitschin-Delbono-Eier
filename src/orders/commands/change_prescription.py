from django.core.files import File
from django.db import transaction

from orders.models import Order


@transaction.atomic
def attach_order_prescription(user_id, order_id, prescription: File, seal=None):
    """Stores the client's prescription while no quote is accepted."""

    order = Order.objects.select_for_update(of=('self',)).get(
        pk=order_id,
        client_account__user_id=user_id,
    )
    order.attach_prescription(prescription)
    order.prescription_seal = seal
    order.save(update_fields=['prescription', 'prescription_seal'])
    return order


@transaction.atomic
def remove_order_prescription(user_id, order_id):
    """Removes the client's prescription while no quote is accepted."""

    order = Order.objects.select_for_update(of=('self',)).get(
        pk=order_id,
        client_account__user_id=user_id,
    )
    if not order.prescription:
        return order
    order.remove_prescription()
    order.save(update_fields=['prescription', 'prescription_seal'])
    return order
