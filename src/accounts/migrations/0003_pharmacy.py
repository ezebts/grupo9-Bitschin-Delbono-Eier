import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.contrib.gis.geos import Point
from django.db import migrations, models

KEY_OPENING_HOURS_BY_DAY = """
UPDATE accounts_pharmacyaccount
SET opening_hours = jsonb_build_object(
    'slot',
    COALESCE(
        (
            SELECT jsonb_object_agg(item ->> 'name', item)
            FROM jsonb_array_elements(opening_hours -> 'slots') AS item
            WHERE COALESCE(item ->> 'name', '') <> ''
        ),
        '{}'::jsonb
    )
)
WHERE jsonb_typeof(opening_hours -> 'slots') = 'array'
"""

NEST_OPENING_HOURS_SLOT = """
UPDATE accounts_pharmacyaccount
SET opening_hours = jsonb_build_object('slot', opening_hours)
WHERE jsonb_typeof(opening_hours) = 'object'
  AND opening_hours <> '{}'::jsonb
  AND NOT (opening_hours ? 'slot')
"""


def enable_postgis(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    register = getattr(schema_editor.connection, 'register_geometry_adapters', None)
    if register is not None:
        register(schema_editor.connection.connection, True)


def copy_coordinates(apps, schema_editor):
    account_model = apps.get_model('accounts', 'PharmacyAccount')
    for account in account_model.objects.all():
        raw = account._location or {}
        coordinates = raw.get('coordinates') or {}
        latitude = coordinates.get('latitude')
        longitude = coordinates.get('longitude')
        if latitude is None or longitude is None:
            continue
        account.coordinates = Point(float(longitude), float(latitude), srid=4326)
        account.save(update_fields=['coordinates'])


def migrate_opening_hours(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(KEY_OPENING_HOURS_BY_DAY)
    schema_editor.execute(NEST_OPENING_HOURS_SLOT)


def copy_pharmacies(apps, schema_editor):
    pharmacy_model = apps.get_model('accounts', 'Pharmacy')
    account_model = apps.get_model('accounts', 'PharmacyAccount')
    for account in account_model.objects.all():
        account.pharmacy = pharmacy_model.objects.create(
            visible=account.visible,
            kind=account.kind,
            trade_name=account.trade_name,
            request_email=account.request_email,
            _phone=account._phone,
            website=account.website,
            _location=account._location,
            coordinates=account.coordinates,
            _opening_hours=account._opening_hours,
            _delivery_terms=account._delivery_terms,
            _preparation_tags=account._preparation_tags,
        )
        account.save(update_fields=['pharmacy'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_client_and_pharmacy_accounts'),
    ]

    operations = [
        migrations.RunPython(enable_postgis, migrations.RunPython.noop),
        migrations.AddField(
            model_name='user',
            name='_timezone',
            field=models.CharField(
                blank=True,
                db_column='timezone',
                default='America/Argentina/Buenos_Aires',
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name='pharmacyaccount',
            name='coordinates',
            field=django.contrib.gis.db.models.fields.PointField(
                blank=True,
                null=True,
                srid=4326,
            ),
        ),
        migrations.RunPython(copy_coordinates, migrations.RunPython.noop),
        migrations.RunPython(migrate_opening_hours, migrations.RunPython.noop),
        migrations.CreateModel(
            name='Pharmacy',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('visible', models.BooleanField(default=True)),
                (
                    'kind',
                    models.CharField(
                        blank=True,
                        choices=[
                            (
                                'pharmacy_with_lab',
                                'Farmacia con laboratorio magistral',
                            ),
                            ('preparation_lab', 'Laboratorio de preparaciones'),
                        ],
                        max_length=32,
                    ),
                ),
                ('trade_name', models.CharField(blank=True, max_length=150)),
                ('request_email', models.EmailField(blank=True, max_length=254)),
                (
                    '_phone',
                    models.CharField(blank=True, db_column='phone', max_length=20),
                ),
                ('website', models.URLField(blank=True)),
                (
                    '_location',
                    models.JSONField(blank=True, db_column='location', default=dict),
                ),
                (
                    'coordinates',
                    django.contrib.gis.db.models.fields.PointField(
                        blank=True,
                        null=True,
                        srid=4326,
                    ),
                ),
                (
                    '_opening_hours',
                    models.JSONField(
                        blank=True,
                        db_column='opening_hours',
                        default=dict,
                    ),
                ),
                (
                    '_delivery_terms',
                    models.JSONField(
                        blank=True,
                        db_column='delivery_terms',
                        default=dict,
                    ),
                ),
                (
                    '_preparation_tags',
                    models.JSONField(
                        blank=True,
                        db_column='preparation_tags',
                        default=list,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='pharmacyaccount',
            name='pharmacy',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accounts',
                to='accounts.pharmacy',
            ),
        ),
        migrations.RunPython(copy_pharmacies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='pharmacyaccount',
            name='pharmacy',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accounts',
                to='accounts.pharmacy',
            ),
        ),
        migrations.RemoveField(model_name='pharmacyaccount', name='visible'),
        migrations.RemoveField(model_name='pharmacyaccount', name='kind'),
        migrations.RemoveField(model_name='pharmacyaccount', name='trade_name'),
        migrations.RemoveField(model_name='pharmacyaccount', name='request_email'),
        migrations.RemoveField(model_name='pharmacyaccount', name='_phone'),
        migrations.RemoveField(model_name='pharmacyaccount', name='website'),
        migrations.RemoveField(model_name='pharmacyaccount', name='_location'),
        migrations.RemoveField(model_name='pharmacyaccount', name='coordinates'),
        migrations.RemoveField(model_name='pharmacyaccount', name='_opening_hours'),
        migrations.RemoveField(model_name='pharmacyaccount', name='_delivery_terms'),
        migrations.RemoveField(
            model_name='pharmacyaccount',
            name='_preparation_tags',
        ),
    ]
