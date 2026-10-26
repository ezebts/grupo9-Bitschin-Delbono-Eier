import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('accounts', '0008_pharmacy_score'),
        ('orders', '0006_order_status_events'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
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
                    'score',
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                ('comment', models.CharField(blank=True, max_length=280)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'author',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='reviews',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'quote_request',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='reviews',
                        to='orders.quoterequest',
                    ),
                ),
            ],
            options={
                'ordering': ('-created_at',),
                'constraints': [
                    models.UniqueConstraint(
                        fields=('quote_request',),
                        name='unique_review_per_quote_request',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(('score__gte', 1), ('score__lte', 5)),
                        name='review_score_between_1_and_5',
                    ),
                ],
            },
        ),
    ]
