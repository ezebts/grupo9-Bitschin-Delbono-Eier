import io
import json
from urllib.error import URLError

import pytest
from django.core.cache import cache

from shared import places
from shared.places import Place, PlaceSearchUnavailableError, search_places
from shared.values import Coordinates

CABA = 'Ciudad Autónoma de Buenos Aires'


def _feature(countrycode, longitude, latitude, **properties):
    return {
        'geometry': {'coordinates': [longitude, latitude]},
        'properties': {'countrycode': countrycode, **properties},
    }


@pytest.fixture(autouse=True)
def empty_cache():
    cache.clear()


def test_search_keeps_unique_places_in_argentina(monkeypatch):
    santa_fe = {'street': 'Avenida Santa Fe', 'housenumber': '3820', 'city': CABA}
    features = [
        _feature('AR', -58.4174826, -34.5842582, district='Palermo', **santa_fe),
        _feature('AR', -58.4175, -34.5843, district='Palermo', **santa_fe),
        _feature('CL', -70.6213, -33.4291, street='Avenida Providencia'),
    ]
    answer = json.dumps({'features': features}).encode()
    monkeypatch.setattr(places, 'urlopen', lambda *_args, **_kwargs: io.BytesIO(answer))

    found = search_places('  av santa fe   3820 ')

    assert found == (
        Place(
            f'Avenida Santa Fe 3820, Palermo, {CABA}',
            Coordinates(-34.5842582, -58.4174826),
        ),
    )


def test_search_reports_an_unavailable_service(monkeypatch):
    def failing_urlopen(*_args, **_kwargs):
        reason = 'timed out'
        raise URLError(reason)

    monkeypatch.setattr(places, 'urlopen', failing_urlopen)

    with pytest.raises(PlaceSearchUnavailableError):
        search_places('Palermo')
