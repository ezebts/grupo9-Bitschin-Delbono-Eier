from django.conf import settings
from django.db import migrations


def configure_site(apps, schema_editor):
    site_model = apps.get_model('sites', 'Site')
    site_model.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={
            'domain': settings.HOST,
            'name': 'Magistral',
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(configure_site, migrations.RunPython.noop),
    ]
