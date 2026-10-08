import accounts.models.clients
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

PHARMACY = 'pharmacy'


def create_missing_accounts(apps, schema_editor):
    user_model = apps.get_model('accounts', 'User')
    client_account_model = apps.get_model('accounts', 'ClientAccount')
    pharmacy_account_model = apps.get_model('accounts', 'PharmacyAccount')
    for user in user_model.objects.iterator():
        if user.role == PHARMACY:
            pharmacy_account_model.objects.get_or_create(user=user)
            continue
        client_account_model.objects.get_or_create(
            user=user,
            defaults={
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientAccount',
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
                ('first_name', models.CharField(max_length=150)),
                ('last_name', models.CharField(max_length=150)),
                (
                    '_phone',
                    models.CharField(blank=True, db_column='phone', max_length=20),
                ),
                ('health_insurance_number', models.CharField(blank=True, max_length=40)),
                (
                    '_location',
                    models.JSONField(blank=True, db_column='location', default=dict),
                ),
                ('search_radius', models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    '_mail_preferences',
                    models.JSONField(
                        blank=True,
                        db_column='mail_preferences',
                        default=accounts.models.clients.default_mail_preferences,
                    ),
                ),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='client_account',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='PharmacyAccount',
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
                ('legal_name', models.CharField(blank=True, max_length=150)),
                (
                    '_cuit',
                    models.CharField(blank=True, db_column='cuit', max_length=11),
                ),
                ('technical_director', models.CharField(blank=True, max_length=150)),
                ('license', models.CharField(blank=True, max_length=40)),
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
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='pharmacy_account',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.RunPython(create_missing_accounts, migrations.RunPython.noop),
    ]
