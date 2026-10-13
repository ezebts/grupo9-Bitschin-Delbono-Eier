from django.conf import settings
from django.contrib.sites.models import Site


def absolute_url(path):
    domain = Site.objects.get_current().domain
    if settings.DEBUG:
        domain = 'localhost:8000'
    scheme = 'http' if settings.DEBUG else 'https'
    return f'{scheme}://{domain}{path}'
