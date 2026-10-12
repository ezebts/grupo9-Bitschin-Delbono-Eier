from decimal import Decimal

import orders.models
from django.db import migrations, models


def _money_payload(currency, amount):
    decimal_places = 2
    normalized = Decimal(str(amount)).quantize(
        Decimal('0.1') ** decimal_places,
    )
    return {
        'amount': format(normalized, 'f'),
        'currency': currency,
        'decimal_places': decimal_places,
        'rounding': 'ROUND_HALF_EVEN',
    }


def copy_quote_money_fields(apps, schema_editor):
    quote_request = apps.get_model('orders', 'QuoteRequest')
    for row in quote_request.objects.all().iterator():
        updates = {
            '_delivery_cost': _money_payload(
                row.delivery_cost_currency,
                row.delivery_cost,
            ),
        }
        if row.price is not None:
            updates['_price'] = _money_payload(row.price_currency, row.price)
        quote_request.objects.filter(pk=row.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ('orders', '0004_quote_currencies'),
    ]

    operations = [  # noqa: RUF012
        migrations.AddField(
            model_name='quoterequest',
            name='_delivery_cost',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='_price',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunPython(copy_quote_money_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='quoterequest',
            name='delivery_cost',
        ),
        migrations.RemoveField(
            model_name='quoterequest',
            name='delivery_cost_currency',
        ),
        migrations.RemoveField(
            model_name='quoterequest',
            name='price',
        ),
        migrations.RemoveField(
            model_name='quoterequest',
            name='price_currency',
        ),
        migrations.AlterField(
            model_name='quoterequest',
            name='_delivery_cost',
            field=models.JSONField(
                blank=True,
                default=orders.models._zero_delivery_cost,
            ),
        ),
    ]
