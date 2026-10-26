from decimal import Decimal

from django.db.models import Avg
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Pharmacy
from reviews.models import Review


@receiver(post_save, sender=Review)
def refresh_pharmacy_score(sender, instance, **kwargs):  # noqa: ARG001
    pharmacy_id = instance.quote_request.pharmacy_id
    average = Review.objects.filter(quote_request__pharmacy_id=pharmacy_id).aggregate(
        average=Avg('score'),
    )['average']
    score = None if average is None else Decimal(average).quantize(Decimal('0.1'))
    Pharmacy.objects.filter(pk=pharmacy_id).update(score=score)
