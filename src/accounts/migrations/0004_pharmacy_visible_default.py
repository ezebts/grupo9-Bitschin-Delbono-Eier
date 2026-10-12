from django.db import migrations, models


def hide_incomplete_pharmacies(apps, schema_editor):
    pharmacy_model = apps.get_model('accounts', 'Pharmacy')
    pharmacy_model.objects.filter(visible=True).filter(
        models.Q(trade_name='')
        | models.Q(request_email='')
        | models.Q(coordinates__isnull=True),
    ).update(visible=False)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_pharmacy'),
    ]

    operations = [
        migrations.RunPython(
            hide_incomplete_pharmacies,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='pharmacy',
            name='visible',
            field=models.BooleanField(default=False),
        ),
    ]
