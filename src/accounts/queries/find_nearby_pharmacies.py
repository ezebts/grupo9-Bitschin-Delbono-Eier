from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Prefetch

from accounts.models import Pharmacy, PharmacyKind, PreparationTag
from accounts.models.clients import SearchRadius
from orders.models import QuoteRequest
from reviews.models import Review
from shared.values import Coordinates

MISSING_ADDRESS = 'Dirección no informada'
MISSING_KIND = 'Farmacia'
MISSING_HOURS = 'Horario no informado'


@dataclass(frozen=True)
class PharmacyReviewCard:
    initials: str
    name: str
    score: int
    comment: str
    created_at: datetime


@dataclass(frozen=True)
class NearbyPharmacy:
    id: int
    name: str
    kind_label: str
    is_laboratory: bool
    distance_km: float
    address: str
    hours: str
    tags: tuple[str, ...]
    latitude: float
    longitude: float
    score: Decimal | None
    reviews: tuple[PharmacyReviewCard, ...]


def find_nearby_pharmacies(  # noqa: PLR0913
    origin: Coordinates,
    *,
    radius_km: SearchRadius,
    include_pharmacies: bool,
    include_labs: bool,
    open_now: bool,
    home_delivery: bool,
    timezone: ZoneInfo,
    preparation_tag: PreparationTag | None = None,
    min_score: int | None = None,
) -> tuple[NearbyPharmacy, ...]:
    """Lists visible pharmacies inside the search radius."""

    now = datetime.now(timezone)

    kinds = []
    if include_pharmacies:
        kinds.extend((PharmacyKind.PHARMACY_WITH_LAB, ''))

    if include_labs:
        kinds.append(PharmacyKind.PREPARATION_LAB)

    if not kinds:
        return ()

    nearby_pharmacies = Pharmacy.objects.filter(
        visible=True,
        kind__in=kinds,
    ).within(origin, radius_km.km)

    if home_delivery:
        nearby_pharmacies = nearby_pharmacies.filter(
            _delivery_terms__home_delivery=True,
        )

    if open_now:
        nearby_pharmacies = nearby_pharmacies.open_at(now)

    if preparation_tag is not None:
        nearby_pharmacies = nearby_pharmacies.filter(
            _preparation_tags__icontains=preparation_tag.value,
        )

    if min_score is not None:
        nearby_pharmacies = nearby_pharmacies.filter(score__gte=min_score)

    nearby_pharmacies = nearby_pharmacies.prefetch_related(
        Prefetch(
            'quote_requests',
            queryset=QuoteRequest.objects.order_by(
                '-reviews__created_at',
                '-reviews__pk',
            ).prefetch_related(
                Prefetch(
                    'reviews',
                    queryset=Review.objects.select_related('author'),
                ),
            ),
        ),
    )

    return tuple(
        NearbyPharmacy(
            id=pharmacy.pk,
            name=pharmacy.trade_name,
            kind_label=(
                PharmacyKind(pharmacy.kind).label if pharmacy.kind else MISSING_KIND
            ),
            is_laboratory=pharmacy.is_laboratory,
            distance_km=pharmacy.distance.km,
            address=pharmacy.location.format() or MISSING_ADDRESS,
            hours=(
                pharmacy.opening_hours.format(now)
                if pharmacy.opening_hours
                else MISSING_HOURS
            ),
            tags=tuple(sorted(tag.label for tag in pharmacy.preparation_tags)),
            latitude=pharmacy.location.coordinates.latitude,
            longitude=pharmacy.location.coordinates.longitude,
            score=pharmacy.score,
            reviews=tuple(
                PharmacyReviewCard(
                    initials=review.author.get_initials(),
                    name=review.author.get_full_name(),
                    score=review.score,
                    comment=review.comment,
                    created_at=review.created_at,
                )
                for quote_request in pharmacy.quote_requests.all()
                for review in quote_request.reviews.all()
            ),
        )
        for pharmacy in nearby_pharmacies
    )
