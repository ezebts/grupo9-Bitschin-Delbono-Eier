from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ('orders', '0003_quoterequest_currency'),
    ]

    operations = [  # noqa: RUF012
        migrations.RenameField(
            model_name='quoterequest',
            old_name='currency',
            new_name='price_currency',
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='delivery_cost_currency',
            field=models.CharField(
                choices=[('ARS', 'ARS'), ('USD', 'USD')],
                default='ARS',
                max_length=3,
            ),
        ),
    ]
