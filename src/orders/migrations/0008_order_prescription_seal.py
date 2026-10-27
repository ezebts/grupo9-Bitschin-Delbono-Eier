from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0007_order_sealed_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='prescription_seal',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
