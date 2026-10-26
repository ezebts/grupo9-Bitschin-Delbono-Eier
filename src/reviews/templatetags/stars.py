from decimal import ROUND_HALF_UP, Decimal

from django import template

from reviews.models import MAX_SCORE

register = template.Library()


@register.inclusion_tag('reviews/_stars.html')
def stars(score):
    filled = int(Decimal(score).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return {
        'score': score,
        'stars': tuple(index < filled for index in range(MAX_SCORE)),
    }
