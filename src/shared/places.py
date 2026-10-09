import hashlib
import json
from dataclasses import dataclass
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from shared.exceptions import Error
from shared.values import Coordinates, InvalidCoordinatesError


@dataclass(frozen=True)
class PlaceSearchUnavailableError(Error):
    message = _('No pudimos buscar direcciones. Probá de nuevo en un rato.')


@dataclass(frozen=True)
class Place:
    label: str
    coordinates: Coordinates


ARGENTINA_BBOX = '-73.6,-55.1,-53.6,-21.8'
ARGENTINA_CODE = 'AR'
MAX_RESULTS = 5
FETCHED_RESULTS = 15
TIMEOUT_SECONDS = 5
CACHE_SECONDS = 60 * 60 * 24


def search_places(text) -> tuple[Place, ...]:
    """Finds places in Argentina that match a free text."""

    text = ' '.join(text.split())
    params = {'q': text, 'limit': FETCHED_RESULTS, 'bbox': ARGENTINA_BBOX}
    return _cached('search', text.lower(), 'api', params)


def find_place(coordinates: Coordinates) -> Place | None:
    """Finds the place at some coordinates."""

    point = f'{coordinates.latitude:.5f},{coordinates.longitude:.5f}'
    params = {'lat': coordinates.latitude, 'lon': coordinates.longitude, 'limit': 1}
    places = _cached('reverse', point, 'reverse', params)
    return places[0] if places else None


def _cached(kind, query, path, params):
    digest = hashlib.sha256(query.encode()).hexdigest()
    return cache.get_or_set(
        f'places:{kind}:{digest}',
        lambda: _fetch(path, params),
        CACHE_SECONDS,
    )


def _fetch(path, params):
    url = f'{settings.PHOTON_URL}/{path}/?{urlencode(params)}'
    request = Request(url, headers={'User-Agent': settings.PHOTON_USER_AGENT})  # noqa: S310
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            features = json.load(response)['features']
    except (OSError, HTTPException, ValueError, KeyError, TypeError) as error:
        raise PlaceSearchUnavailableError from error
    places = {}
    for feature in features:
        place = _place(feature)
        if place:
            places.setdefault(place.label, place)
    return tuple(places.values())[:MAX_RESULTS]


def _place(feature):
    properties = feature.get('properties', {})
    if properties.get('countrycode') != ARGENTINA_CODE:
        return None
    street = ' '.join(
        part
        for part in (properties.get('street'), properties.get('housenumber'))
        if part
    )
    parts = (
        properties.get('name'),
        street,
        properties.get('district') or properties.get('locality'),
        properties.get('city') or properties.get('state'),
    )
    label = ', '.join(dict.fromkeys(part for part in parts if part))
    try:
        longitude, latitude = feature['geometry']['coordinates']
        coordinates = Coordinates.create(latitude, longitude)
    except (KeyError, TypeError, ValueError, InvalidCoordinatesError):
        return None
    return Place(label, coordinates) if label else None
