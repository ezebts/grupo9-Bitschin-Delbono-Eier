from django.contrib.gis.geos import Point
from django.db import migrations

LOCALITY = 'Rafaela'
POSTAL_CODE = '2300'
SRID = 4326

PHARMACIES = (
    (
        'Farmacia ABOAL',
        'ezequiel.bitschin+farmacia.aboal@gmail.com',
        'Av. Aristóbulo del Valle 1171',
        -31.259448,
        -61.480945,
    ),
    (
        'Farmacia ABRATE',
        'ezequiel.bitschin+farmacia.abrate@gmail.com',
        'Av. Luis Fanti 102 y Colón',
        -31.261761,
        -61.495328,
    ),
    (
        'Farmacia BERNINI',
        'ezequiel.bitschin+farmacia.bernini@gmail.com',
        'Av. Luis Fanti 1510',
        -31.259424,
        -61.509983,
    ),
    (
        'Farmacia BLATTER',
        'ezequiel.bitschin+farmacia.blatter@gmail.com',
        'Av. Santa Fe 1460',
        -31.255223,
        -61.476875,
    ),
    (
        'Farmacia BRUERA',
        'ezequiel.bitschin+farmacia.bruera@gmail.com',
        'Tucumán 130',
        -31.252633,
        -61.484756,
    ),
    (
        'Farmacia CAGNOTTI',
        'ezequiel.bitschin+farmacia.cagnotti@gmail.com',
        'San Martín 345',
        -31.252345,
        -61.487806,
    ),
    (
        'Farmacia CABALLERO',
        'ezequiel.bitschin+farmacia.caballero@gmail.com',
        'Sacripanti 1740',
        -31.266831,
        -61.502510,
    ),
    (
        'Farmacia CASTELLANO',
        'ezequiel.bitschin+farmacia.castellano@gmail.com',
        'Bv. Lehmann y Agustín Alvarez',
        -31.246939,
        -61.490304,
    ),
    (
        'Farmacia CECCHI',
        'ezequiel.bitschin+farmacia.cecchi@gmail.com',
        'Bv. Lehmann 747',
        -31.245456,
        -61.490069,
    ),
    (
        'Farmacia CORACH',
        'ezequiel.bitschin+farmacia.corach@gmail.com',
        'Av. Santa Fe 417',
        -31.253452,
        -61.487308,
    ),
    (
        'Farmacia CORNATOSKY',
        'ezequiel.bitschin+farmacia.cornatosky@gmail.com',
        'Av. Fader 567',
        -31.264298,
        -61.488706,
    ),
    (
        "Farmacia D'AGOSTINO",
        'ezequiel.bitschin+farmacia.dagostino@gmail.com',
        'Jorge Newbery 396',
        -31.253314,
        -61.467368,
    ),
    (
        'Farmacia DARDATI',
        'ezequiel.bitschin+farmacia.dardati@gmail.com',
        'Lavalle 64',
        -31.252176,
        -61.490501,
    ),
    (
        'Farmacia DECHIARA',
        'ezequiel.bitschin+farmacia.dechiara@gmail.com',
        'Av. Mitre 309',
        -31.252913,
        -61.482299,
    ),
    (
        'Farmacia DELBINO',
        'ezequiel.bitschin+farmacia.delbino@gmail.com',
        'Av. Mitre 1148',
        -31.251490,
        -61.475887,
    ),
    (
        'Farmacia ELSENER',
        'ezequiel.bitschin+farmacia.elsener@gmail.com',
        'Vieytes 169',
        -31.270887,
        -61.497870,
    ),
    (
        'Farmacia ESCOBAR',
        'ezequiel.bitschin+farmacia.escobar@gmail.com',
        'Av. Santa Fe 1141',
        -31.254689,
        -61.479921,
    ),
    (
        'Farmacia FOGLIATTI',
        'ezequiel.bitschin+farmacia.fogliatti@gmail.com',
        'Bv. H. Yrigoyen 1338',
        -31.265237,
        -61.494697,
    ),
    (
        'Farmacia GIORGIS',
        'ezequiel.bitschin+farmacia.giorgis@gmail.com',
        'Bv. Roca 1658',
        -31.249634,
        -61.509878,
    ),
    (
        'Farmacia GRIMALDI',
        'ezequiel.bitschin+farmacia.grimaldi@gmail.com',
        'Falucho 30',
        -31.257147,
        -61.493296,
    ),
    (
        'Farmacia GUEMBERENA',
        'ezequiel.bitschin+farmacia.guemberena@gmail.com',
        'Bv. Lehmann 1395',
        -31.240223,
        -61.488800,
    ),
    (
        'Farmacia INGARAMO',
        'ezequiel.bitschin+farmacia.ingaramo@gmail.com',
        'Bv. Roca 197 e Ituzaingó',
        -31.252215,
        -61.493858,
    ),
    (
        'Farmacia LEIGGENER',
        'ezequiel.bitschin+farmacia.leiggener@gmail.com',
        'Av. Italia 1857',
        -31.238327,
        -61.474262,
    ),
    (
        'Farmacia LONGONI',
        'ezequiel.bitschin+farmacia.longoni@gmail.com',
        'Sarmiento 190',
        -31.251190,
        -61.489195,
    ),
    (
        'Farmacia MAINERO',
        'ezequiel.bitschin+farmacia.mainero@gmail.com',
        'Suipacha 413',
        -31.255334,
        -61.499695,
    ),
    (
        'Farmacia MODENESI',
        'ezequiel.bitschin+farmacia.modenesi@gmail.com',
        'Av. Ernesto Salva 1016',
        -31.241785,
        -61.500401,
    ),
    (
        'Farmacia MORBIDONI',
        'ezequiel.bitschin+farmacia.morbidoni@gmail.com',
        'Av. Ernesto Salva 34',
        -31.243222,
        -61.490009,
    ),
    (
        'Farmacia MORELLO',
        'ezequiel.bitschin+farmacia.morello@gmail.com',
        'Av. Brasil 1114',
        -31.245456,
        -61.477274,
    ),
    (
        'Farmacia MORENO',
        'ezequiel.bitschin+farmacia.moreno@gmail.com',
        'Moreno 226',
        -31.251338,
        -61.493934,
    ),
    (
        'Farmacia OPERTO',
        'ezequiel.bitschin+farmacia.operto@gmail.com',
        'Bv. Yrigoyen 229',
        -31.254729,
        -61.492390,
    ),
    (
        'Farmacia PAUTASSO',
        'ezequiel.bitschin+farmacia.pautasso@gmail.com',
        'Rosario 392',
        -31.247483,
        -61.500509,
    ),
    (
        'Farmacia PUIG',
        'ezequiel.bitschin+farmacia.puig@gmail.com',
        'Av. Brasil 470',
        -31.244212,
        -61.484349,
    ),
    (
        'Farmacia ROSSI',
        'ezequiel.bitschin+farmacia.rossi@gmail.com',
        'Rosario 698',
        -31.244704,
        -61.499854,
    ),
    (
        'Farmacia SELLO',
        'ezequiel.bitschin+farmacia.sello@gmail.com',
        'Av. Roca 653',
        -31.251653,
        -61.499008,
    ),
    (
        'Farmacia SERRA',
        'ezequiel.bitschin+farmacia.serra@gmail.com',
        'Falucho 1325',
        -31.255117,
        -61.507546,
    ),
    (
        'Farmacia SIMONCINI',
        'ezequiel.bitschin+farmacia.simoncini@gmail.com',
        'Av. Aristóbulo del Valle 132',
        -31.257404,
        -61.491668,
    ),
    (
        'Farmacia SUDANO',
        'ezequiel.bitschin+farmacia.sudano@gmail.com',
        'Colón 54',
        -31.253026,
        -61.492980,
    ),
    (
        'Farmacia TESSIO',
        'ezequiel.bitschin+farmacia.tessio@gmail.com',
        'Aconcagua 602',
        -31.251691,
        -61.463327,
    ),
    (
        'Farmacia TIBALDI',
        'ezequiel.bitschin+farmacia.tibaldi@gmail.com',
        'Ernesto Salva 317',
        -31.242771,
        -61.492680,
    ),
    (
        'Farmacia TOMATIS',
        'ezequiel.bitschin+farmacia.tomatis@gmail.com',
        'Neuquén 148',
        -31.228203,
        -61.488018,
    ),
    (
        'Farmacia TURINO',
        'ezequiel.bitschin+farmacia.turino@gmail.com',
        'España 1135',
        -31.245600,
        -61.474437,
    ),
    (
        'Farmacia WALTER',
        'ezequiel.bitschin+farmacia.walter@gmail.com',
        'Lavalle y Sarmiento',
        -31.251026,
        -61.490161,
    ),
    (
        'Farmacia ZEBALLOS',
        'ezequiel.bitschin+farmacia.zeballos@gmail.com',
        'Simón de Iriondo 1234',
        -31.238228,
        -61.507530,
    ),
)


def load_adhered_pharmacies(apps, schema_editor):

    if schema_editor.connection.vendor != 'postgresql':
        return

    pharmacy_model = apps.get_model('accounts', 'Pharmacy')

    pharmacy_model.objects.bulk_create(
        [
            pharmacy_model(
                visible=True,
                kind='',
                trade_name=trade_name,
                request_email=request_email,
                _phone='',
                website='',
                _location={
                    'address': address,
                    'locality': LOCALITY,
                    'postal_code': POSTAL_CODE,
                    'coordinates': {
                        'latitude': latitude,
                        'longitude': longitude,
                    },
                },
                coordinates=Point(longitude, latitude, srid=SRID),
                _opening_hours={},
                _delivery_terms={},
                _preparation_tags=[],
                _mail_preferences={'on_reply': True, 'on_quote_status': True},
            )
            for (
                trade_name,
                request_email,
                address,
                latitude,
                longitude,
            ) in PHARMACIES
        ],
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_pharmacy_mail_preferences'),
    ]

    operations = [
        migrations.RunPython(
            load_adhered_pharmacies,
            migrations.RunPython.noop,
        ),
    ]
