from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ('orders', '0001_initial'),
    ]

    operations = [  # noqa: RUF012
        migrations.AddField(
            model_name='quoterequest',
            name='price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='preparation_time',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='_delivery_preferences',
            field=models.JSONField(
                db_column='delivery_preferences',
                default=list,
            ),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='delivery_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='valid_until',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='quoted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
