from dataclasses import dataclass
from datetime import datetime

from reviews.models import Review


@dataclass(frozen=True)
class ConversationReview:
    score: int
    comment: str
    name: str
    initials: str
    created_at: datetime


def get_conversation_review(conversation_id) -> ConversationReview | None:
    """Reads the review a client already left on one conversation."""

    review = (
        Review.objects.select_related('author')
        .filter(quote_request__conversation__pk=conversation_id)
        .first()
    )
    if review is None:
        return None

    return ConversationReview(
        score=review.score,
        comment=review.comment,
        name=review.author.get_full_name(),
        initials=review.author.get_initials(),
        created_at=review.created_at,
    )
