from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0007_load_adhered_pharmacies'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacy',
            name='score',
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=2,
                null=True,
            ),
        ),
    ]
