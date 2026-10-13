from dataclasses import dataclass

from django.db import transaction

from accounts.models import Pharmacy
from shared.values import Coordinates, Location

LOCALITY = 'Rafaela'
POSTAL_CODE = '2300'

_PHARMACIES = (
    (
        'Farmacia ABOAL',
        'Av. Aristóbulo del Valle 1171',
        -31.259448,
        -61.480945,
    ),
    (
        'Farmacia ABRATE',
        'Av. Luis Fanti 102 y Colón',
        -31.261761,
        -61.495328,
    ),
    (
        'Farmacia BERNINI',
        'Av. Luis Fanti 1510',
        -31.259424,
        -61.509983,
    ),
    (
        'Farmacia BLATTER',
        'Av. Santa Fe 1460',
        -31.255223,
        -61.476875,
    ),
    (
        'Farmacia BRUERA',
        'Tucumán 130',
        -31.252633,
        -61.484756,
    ),
    (
        'Farmacia CAGNOTTI',
        'San Martín 345',
        -31.252345,
        -61.487806,
    ),
    (
        'Farmacia CABALLERO',
        'Sacripanti 1740',
        -31.266831,
        -61.502510,
    ),
    (
        'Farmacia CASTELLANO',
        'Bv. Lehmann y Agustín Alvarez',
        -31.246939,
        -61.490304,
    ),
    (
        'Farmacia CECCHI',
        'Bv. Lehmann 747',
        -31.245456,
        -61.490069,
    ),
    (
        'Farmacia CORACH',
        'Av. Santa Fe 417',
        -31.253452,
        -61.487308,
    ),
    (
        'Farmacia CORNATOSKY',
        'Av. Fader 567',
        -31.264298,
        -61.488706,
    ),
    (
        "Farmacia D'AGOSTINO",
        'Jorge Newbery 396',
        -31.253314,
        -61.467368,
    ),
    (
        'Farmacia DARDATI',
        'Lavalle 64',
        -31.252176,
        -61.490501,
    ),
    (
        'Farmacia DECHIARA',
        'Av. Mitre 309',
        -31.252913,
        -61.482299,
    ),
    (
        'Farmacia DELBINO',
        'Av. Mitre 1148',
        -31.251490,
        -61.475887,
    ),
    (
        'Farmacia ELSENER',
        'Vieytes 169',
        -31.270887,
        -61.497870,
    ),
    (
        'Farmacia ESCOBAR',
        'Av. Santa Fe 1141',
        -31.254689,
        -61.479921,
    ),
    (
        'Farmacia FOGLIATTI',
        'Bv. H. Yrigoyen 1338',
        -31.265237,
        -61.494697,
    ),
    (
        'Farmacia GIORGIS',
        'Bv. Roca 1658',
        -31.249634,
        -61.509878,
    ),
    (
        'Farmacia GRIMALDI',
        'Falucho 30',
        -31.257147,
        -61.493296,
    ),
    (
        'Farmacia GUEMBERENA',
        'Bv. Lehmann 1395',
        -31.240223,
        -61.488800,
    ),
    (
        'Farmacia INGARAMO',
        'Bv. Roca 197 e Ituzaingó',
        -31.252215,
        -61.493858,
    ),
    (
        'Farmacia LEIGGENER',
        'Av. Italia 1857',
        -31.238327,
        -61.474262,
    ),
    (
        'Farmacia LONGONI',
        'Sarmiento 190',
        -31.251190,
        -61.489195,
    ),
    (
        'Farmacia MAINERO',
        'Suipacha 413',
        -31.255334,
        -61.499695,
    ),
    (
        'Farmacia MODENESI',
        'Av. Ernesto Salva 1016',
        -31.241785,
        -61.500401,
    ),
    (
        'Farmacia MORBIDONI',
        'Av. Ernesto Salva 34',
        -31.243222,
        -61.490009,
    ),
    (
        'Farmacia MORELLO',
        'Av. Brasil 1114',
        -31.245456,
        -61.477274,
    ),
    (
        'Farmacia MORENO',
        'Moreno 226',
        -31.251338,
        -61.493934,
    ),
    (
        'Farmacia OPERTO',
        'Bv. Yrigoyen 229',
        -31.254729,
        -61.492390,
    ),
    (
        'Farmacia PAUTASSO',
        'Rosario 392',
        -31.247483,
        -61.500509,
    ),
    (
        'Farmacia PUIG',
        'Av. Brasil 470',
        -31.244212,
        -61.484349,
    ),
    (
        'Farmacia ROSSI',
        'Rosario 698',
        -31.244704,
        -61.499854,
    ),
    (
        'Farmacia SELLO',
        'Av. Roca 653',
        -31.251653,
        -61.499008,
    ),
    (
        'Farmacia SERRA',
        'Falucho 1325',
        -31.255117,
        -61.507546,
    ),
    (
        'Farmacia SIMONCINI',
        'Av. Aristóbulo del Valle 132',
        -31.257404,
        -61.491668,
    ),
    (
        'Farmacia SUDANO',
        'Colón 54',
        -31.253026,
        -61.492980,
    ),
    (
        'Farmacia TESSIO',
        'Aconcagua 602',
        -31.251691,
        -61.463327,
    ),
    (
        'Farmacia TIBALDI',
        'Ernesto Salva 317',
        -31.242771,
        -61.492680,
    ),
    (
        'Farmacia TOMATIS',
        'Neuquén 148',
        -31.228203,
        -61.488018,
    ),
    (
        'Farmacia TURINO',
        'España 1135',
        -31.245600,
        -61.474437,
    ),
    (
        'Farmacia WALTER',
        'Lavalle y Sarmiento',
        -31.251026,
        -61.490161,
    ),
    (
        'Farmacia ZEBALLOS',
        'Simón de Iriondo 1234',
        -31.238228,
        -61.507530,
    ),
)


@dataclass(frozen=True)
class LoadAdheredPharmaciesResult:
    created: tuple[str, ...]
    already_loaded: tuple[str, ...]


def contact_email(trade_name):
    slug = trade_name.removeprefix('Farmacia ').replace("'", '').lower()
    return f'ezequiel.bitschin+farmacia.{slug}@gmail.com'


def load_adhered_pharmacies():
    """Creates missing Pharmacy rows for the adhered Rafaela pharmacies."""

    created = []
    already_loaded = []

    for trade_name, address, latitude, longitude in _PHARMACIES:
        email = contact_email(trade_name)
        if Pharmacy.objects.filter(request_email=email).exists():
            already_loaded.append(trade_name)
            continue

        _create_pharmacy(trade_name, email, address, latitude, longitude)
        created.append(trade_name)

    return LoadAdheredPharmaciesResult(
        created=tuple(created),
        already_loaded=tuple(already_loaded),
    )


@transaction.atomic
def _create_pharmacy(trade_name, email, address, latitude, longitude):
    pharmacy = Pharmacy()
    pharmacy.update_establishment('', trade_name)
    pharmacy.update_contact_info(email, None, '')
    pharmacy.update_location(
        Location.create(
            address,
            LOCALITY,
            POSTAL_CODE,
            Coordinates.create(latitude, longitude),
        ),
    )
    pharmacy.set_visibility(True)
    pharmacy.save()
