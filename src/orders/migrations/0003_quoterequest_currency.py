from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ('orders', '0002_quote_terms'),
    ]

    operations = [  # noqa: RUF012
        migrations.AddField(
            model_name='quoterequest',
            name='currency',
            field=models.CharField(
                choices=[('ARS', 'ARS'), ('USD', 'USD')],
                default='ARS',
                max_length=3,
            ),
        ),
    ]
