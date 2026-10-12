from django.db import models
from django.db.models import Case, CharField, Count, Exists, OuterRef, Q, Value, When


def prescriptions_path(instance, filename):
    return f'orders/prescriptions/{instance.pk}/{filename}'


class Urgency(models.TextChoices):
    AS_SOON_AS_POSSIBLE = 'as_soon_as_possible', 'Lo antes posible'
    THIS_WEEK = 'this_week', 'Esta semana'
    NO_RUSH = 'no_rush', 'Sin apuro'


class DeliveryPreference(models.TextChoices):
    PICKUP = 'pickup', 'Retiro en farmacia'
    HOME_DELIVERY = 'home_delivery', 'Envío a domicilio'


class QuoteRequestStatus(models.TextChoices):
    WAITING = 'waiting', 'Esperando'
    QUOTED = 'quoted', 'Cotizado'
    DECLINED = 'declined', 'Rechazado por la farmacia'
    WITHDRAWN = 'withdrawn', 'Presupuesto retirado'
    REJECTED = 'rejected', 'Rechazado por el cliente'
    ACCEPTED = 'accepted', 'Aceptado'
    NOT_CHOSEN = 'not_chosen', 'No elegido'


class OrderProgress(models.TextChoices):
    WAITING = 'waiting', 'Esperando presupuestos'
    QUOTED = 'quoted', 'Presupuestos recibidos'
    IN_PROGRESS = 'in_progress', 'En preparación'
    FINISHED = 'finished', 'Finalizado'


class OrderQuerySet(models.QuerySet):
    def with_progress(self):

        has_accepted = Exists(
            QuoteRequest.objects.filter(
                order=OuterRef('pk'),
                status=QuoteRequestStatus.ACCEPTED,
            )
        )

        has_quoted = Exists(
            QuoteRequest.objects.filter(
                order=OuterRef('pk'),
                status=QuoteRequestStatus.QUOTED,
            )
        )

        return self.alias(
            has_accepted=has_accepted,
            has_quoted=has_quoted,
        ).annotate(
            progress_code=Case(
                When(has_accepted=True, then=Value(OrderProgress.IN_PROGRESS)),
                When(has_quoted=True, then=Value(OrderProgress.QUOTED)),
                default=Value(OrderProgress.WAITING),
                output_field=CharField(),
            ),
        )

    def with_quote_counts(self):
        received = Q(
            quote_requests__status__in=(
                QuoteRequestStatus.QUOTED,
                QuoteRequestStatus.ACCEPTED,
                QuoteRequestStatus.REJECTED,
                QuoteRequestStatus.WITHDRAWN,
            ),
        )

        return self.annotate(
            quotes_total=Count('quote_requests'),
            quotes_received=Count('quote_requests', filter=received),
        )


class Order(models.Model):
    client_account = models.ForeignKey(
        'accounts.ClientAccount',
        on_delete=models.PROTECT,
        related_name='orders',
    )

    code_width = 5

    code = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        default=None,
    )

    preparation_tag = models.CharField(max_length=32)

    formula = models.CharField(max_length=2000)

    presentation = models.CharField(max_length=60)

    urgency = models.CharField(max_length=32, choices=Urgency.choices)

    _delivery_preferences = models.JSONField(
        default=list,
        db_column='delivery_preferences',
    )

    note = models.CharField(max_length=1000, blank=True)

    prescription = models.FileField(
        upload_to=prescriptions_path,
        blank=True,
        max_length=255,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.code or ''

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.code:
            return
        self.code = f'MG-{self.pk:0{self.code_width}d}'
        super().save(update_fields=['code'])

    def attach_prescription(self, prescription):
        self.prescription = prescription

    @classmethod
    def create(  # noqa: PLR0913, PLR0917
        cls,
        client_account,
        formula,
        presentation,
        urgency,
        delivery_preferences,
        note,
        preparation_tag,
    ):
        return cls(
            client_account=client_account,
            formula=formula,
            presentation=presentation,
            urgency=urgency,
            _delivery_preferences=list(delivery_preferences),
            note=note,
            preparation_tag=preparation_tag,
        )

    @property
    def delivery_preferences(self):
        return tuple(self._delivery_preferences)

    @property
    def progress(self):
        statuses = {quote.status for quote in self.quote_requests.all()}
        if QuoteRequestStatus.ACCEPTED in statuses:
            return OrderProgress.IN_PROGRESS
        if QuoteRequestStatus.QUOTED in statuses:
            return OrderProgress.QUOTED
        return OrderProgress.WAITING


class QuoteRequest(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='quote_requests',
    )

    pharmacy = models.ForeignKey(
        'accounts.Pharmacy',
        on_delete=models.PROTECT,
        related_name='quote_requests',
    )

    status = models.CharField(
        max_length=16,
        choices=QuoteRequestStatus.choices,
        default=QuoteRequestStatus.WAITING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=('order', 'pharmacy'),
                name='unique_quote_request_per_pharmacy',
            ),
        ]
        ordering = ('created_at',)

    def __str__(self):
        return f'{self.order.code} → {self.pharmacy}'

    @classmethod
    def create(cls, order, pharmacy):
        return cls(
            order=order,
            pharmacy=pharmacy,
            status=QuoteRequestStatus.WAITING,
        )
