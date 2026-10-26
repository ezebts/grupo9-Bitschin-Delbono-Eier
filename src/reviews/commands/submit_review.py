from django.db import transaction

from orders.models import FulfillmentStatus, QuoteRequest, QuoteRequestStatus
from reviews.exceptions import ReviewAlreadySentError, ReviewNotAllowedError
from reviews.models import Review


@transaction.atomic
def submit_review(user_id, conversation_id, score, comment):
    """Stores the client's review of a delivered order."""

    quote_request = (
        QuoteRequest.objects.select_for_update()
        .select_related('order')
        .get(
            conversation__pk=conversation_id,
            order__client_account__user_id=user_id,
            status=QuoteRequestStatus.ACCEPTED,
        )
    )

    if quote_request.order.fulfillment_status != FulfillmentStatus.DELIVERED:
        raise ReviewNotAllowedError

    if Review.objects.filter(quote_request=quote_request).exists():
        raise ReviewAlreadySentError

    return Review.objects.create(
        quote_request=quote_request,
        author_id=user_id,
        score=score,
        comment=comment,
    )
