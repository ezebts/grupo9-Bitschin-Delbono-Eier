import accounts.models.pharmacies
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_user_name_required'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacy',
            name='_mail_preferences',
            field=models.JSONField(
                blank=True,
                db_column='mail_preferences',
                default=accounts.models.pharmacies.PharmacyMailPreferences.default,
            ),
        ),
    ]
