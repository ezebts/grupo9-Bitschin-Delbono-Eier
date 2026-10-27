from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0006_order_status_events'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='formula',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='order',
            name='presentation',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='order',
            name='note',
            field=models.TextField(blank=True),
        ),
    ]
