from django.db import models
from django.db.models import Case, CharField, Count, Exists, OuterRef, Q, Value, When
from django.utils import timezone

from orders.exceptions import (
    ExpiredQuoteError,
    InvalidEstimatedDateError,
    OrderCannotAdvanceError,
    QuoteCannotBeAnsweredError,
    QuoteCannotBeEditedError,
    QuoteCannotBeSubmittedError,
    QuoteCannotBeWithdrawnError,
)
from shared.dataclasses import asdict, from_dict
from shared.values import Money


def _zero_delivery_cost():
    return asdict(Money.ARS(0))


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


class FulfillmentStatus(models.TextChoices):
    ACCEPTED = 'accepted', 'Presupuesto aceptado'
    IN_PREPARATION = 'in_preparation', 'En preparación'
    READY_FOR_PICKUP = 'ready_for_pickup', 'Listo para retirar'
    DELIVERED = 'delivered', 'Entregado'


class OrderQuerySet(models.QuerySet):
    def with_progress(self):

        has_delivered = Exists(
            StatusEvent.objects.filter(
                order=OuterRef('pk'),
                status=FulfillmentStatus.DELIVERED,
            )
        )

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
            has_delivered=has_delivered,
            has_accepted=has_accepted,
            has_quoted=has_quoted,
        ).annotate(
            progress_code=Case(
                When(has_delivered=True, then=Value(OrderProgress.FINISHED)),
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
        if self.fulfillment_status == FulfillmentStatus.DELIVERED:
            return OrderProgress.FINISHED
        statuses = {quote.status for quote in self.quote_requests.all()}
        if QuoteRequestStatus.ACCEPTED in statuses:
            return OrderProgress.IN_PROGRESS
        if QuoteRequestStatus.QUOTED in statuses:
            return OrderProgress.QUOTED
        return OrderProgress.WAITING

    @property
    def fulfillment_status(self):
        event = self.status_events.last()
        return FulfillmentStatus(event.status) if event else None

    def fulfillment_label(self, status):
        if (
            status == FulfillmentStatus.READY_FOR_PICKUP
            and DeliveryPreference.PICKUP not in self.delivery_preferences
        ):
            return 'En camino'
        return FulfillmentStatus(status).label

    def mark_accepted(self):
        return StatusEvent(order=self, status=FulfillmentStatus.ACCEPTED)

    @property
    def next_fulfillment_status(self):
        current = self.fulfillment_status
        if current is None or current == FulfillmentStatus.DELIVERED:
            return None
        statuses = list(FulfillmentStatus)
        return statuses[statuses.index(current) + 1]

    def advance_fulfillment(self, estimated_at, today):
        status = self.next_fulfillment_status
        if status is None:
            raise OrderCannotAdvanceError

        if status != FulfillmentStatus.IN_PREPARATION:
            return StatusEvent(order=self, status=status)

        if estimated_at is None or estimated_at < today:
            raise InvalidEstimatedDateError

        return StatusEvent(order=self, status=status, estimated_at=estimated_at)


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

    _price = models.JSONField(null=True, blank=True)

    preparation_time = models.CharField(max_length=80, blank=True)

    _delivery_preferences = models.JSONField(
        default=list,
        db_column='delivery_preferences',
    )

    _delivery_cost = models.JSONField(default=_zero_delivery_cost, blank=True)

    valid_until = models.DateField(null=True, blank=True)

    quoted_at = models.DateTimeField(null=True, blank=True)

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

    def submit_quote(self):
        if self.status != QuoteRequestStatus.WAITING:
            raise QuoteCannotBeSubmittedError

        self.status = QuoteRequestStatus.QUOTED
        self.quoted_at = timezone.now()

    def update_quote(self):
        if self.status != QuoteRequestStatus.QUOTED:
            raise QuoteCannotBeEditedError

        self.quoted_at = timezone.now()

    def withdraw_quote(self):
        if self.status != QuoteRequestStatus.QUOTED:
            raise QuoteCannotBeWithdrawnError

        self.status = QuoteRequestStatus.WITHDRAWN

    def accept_quote(self, today):
        if self.status != QuoteRequestStatus.QUOTED:
            raise QuoteCannotBeAnsweredError

        if self.valid_until < today:
            raise ExpiredQuoteError

        self.status = QuoteRequestStatus.ACCEPTED

    def reject_quote(self):
        if self.status != QuoteRequestStatus.QUOTED:
            raise QuoteCannotBeAnsweredError

        self.status = QuoteRequestStatus.REJECTED

    def mark_not_chosen(self):
        self.status = QuoteRequestStatus.NOT_CHOSEN

    @property
    def price(self) -> Money | None:
        return from_dict(Money, self._price)

    @property
    def delivery_cost(self) -> Money:
        money = from_dict(Money, self._delivery_cost)
        return money if money is not None else Money.ARS(0)

    def set_quote_terms(
        self,
        *,
        price: Money,
        preparation_time,
        delivery_preferences,
        delivery_cost: Money,
        valid_until,
    ):
        self._price = asdict(price)
        self._delivery_cost = asdict(delivery_cost)
        self.preparation_time = preparation_time
        self._delivery_preferences = list(delivery_preferences)
        self.valid_until = valid_until

    @property
    def delivery_preferences(self):
        return tuple(self._delivery_preferences)

    @classmethod
    def create(cls, order, pharmacy):
        return cls(
            order=order,
            pharmacy=pharmacy,
            status=QuoteRequestStatus.WAITING,
        )


class StatusEvent(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_events',
    )

    status = models.CharField(max_length=32, choices=FulfillmentStatus.choices)

    estimated_at = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')

    def __str__(self):
        return f'{self.order.code} → {self.get_status_display()}'
