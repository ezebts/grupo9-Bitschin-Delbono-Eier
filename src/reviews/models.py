from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

COMMENT_MAX_LENGTH = 140
MIN_SCORE = 1
MAX_SCORE = 5


class Review(models.Model):
    quote_request = models.ForeignKey(
        'orders.QuoteRequest',
        on_delete=models.CASCADE,
        related_name='reviews',
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviews',
    )

    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_SCORE), MaxValueValidator(MAX_SCORE)],
    )

    comment = models.CharField(max_length=COMMENT_MAX_LENGTH, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=('quote_request',),
                name='unique_review_per_quote_request',
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=MIN_SCORE, score__lte=MAX_SCORE),
                name='review_score_between_1_and_5',
            ),
        ]

    def __str__(self):
        return f'{self.score} · {self.quote_request_id}'

    def save(self, *args, **kwargs):
        self.comment = (self.comment or '').strip()
        super().save(*args, **kwargs)
