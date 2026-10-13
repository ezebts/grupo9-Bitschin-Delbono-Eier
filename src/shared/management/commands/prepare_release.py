from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import ProgrammingError


class Command(BaseCommand):
    help = 'Enables PostGIS and points the site at this Render hostname.'

    def handle(self, *args, **options):  # noqa: ARG002
        with connection.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS postgis')

        try:
            site = Site.objects.get(pk=settings.SITE_ID)
        except ProgrammingError:
            return

        site.domain = settings.HOST
        site.name = 'Magistral'
        site.save(update_fields=['domain', 'name'])
