from django.db import transaction

from accounts.models import Pharmacy
from orders.models import Order, QuoteRequest


@transaction.atomic
def request_quote(order_id, pharmacy_id):
    """Asks one pharmacy to quote an order."""

    order = Order.objects.get(pk=order_id)
    pharmacy = Pharmacy.objects.get(pk=pharmacy_id)
    quote_request = QuoteRequest.create(order, pharmacy)
    quote_request.save()
    return quote_request
