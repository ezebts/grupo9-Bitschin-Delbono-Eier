import django.db.models.deletion
import orders.models
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('accounts', '0005_user_name_required'),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
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
                (
                    'code',
                    models.CharField(
                        blank=True,
                        default=None,
                        max_length=32,
                        null=True,
                        unique=True,
                    ),
                ),
                ('preparation_tag', models.CharField(max_length=32)),
                ('formula', models.CharField(max_length=2000)),
                ('presentation', models.CharField(max_length=60)),
                (
                    'urgency',
                    models.CharField(
                        choices=[
                            ('as_soon_as_possible', 'Lo antes posible'),
                            ('this_week', 'Esta semana'),
                            ('no_rush', 'Sin apuro'),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    '_delivery_preferences',
                    models.JSONField(db_column='delivery_preferences', default=list),
                ),
                ('note', models.CharField(blank=True, max_length=1000)),
                (
                    'prescription',
                    models.FileField(
                        blank=True,
                        max_length=255,
                        upload_to=orders.models.prescriptions_path,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'client_account',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='orders',
                        to='accounts.clientaccount',
                    ),
                ),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='QuoteRequest',
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
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('waiting', 'Esperando'),
                            ('quoted', 'Cotizado'),
                            ('declined', 'Rechazado por la farmacia'),
                            ('withdrawn', 'Presupuesto retirado'),
                            ('rejected', 'Rechazado por el cliente'),
                            ('accepted', 'Aceptado'),
                            ('not_chosen', 'No elegido'),
                        ],
                        default='waiting',
                        max_length=16,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='quote_requests',
                        to='orders.order',
                    ),
                ),
                (
                    'pharmacy',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='quote_requests',
                        to='accounts.pharmacy',
                    ),
                ),
            ],
            options={
                'ordering': ('created_at',),
                'constraints': [
                    models.UniqueConstraint(
                        fields=('order', 'pharmacy'),
                        name='unique_quote_request_per_pharmacy',
                    ),
                ],
            },
        ),
    ]
