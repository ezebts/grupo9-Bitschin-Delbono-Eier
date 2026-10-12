from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from accounts.models import Pharmacy, PharmacyKind, PreparationTag
from accounts.models.clients import SearchRadius
from shared.values import Coordinates

MISSING_ADDRESS = 'Dirección no informada'
MISSING_KIND = 'Farmacia'
MISSING_HOURS = 'Horario no informado'


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
    ).within(origin, radius_km.value)

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
        )
        for pharmacy in nearby_pharmacies
    )
