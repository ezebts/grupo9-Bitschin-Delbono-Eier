from django.conf import settings


def absolute_url(path) -> str:
    domain = settings.HOST
    if settings.DEBUG and ':' not in domain:
        domain = f'{domain}:8000'
    scheme = 'http' if settings.DEBUG else 'https'
    return f'{scheme}://{domain}{path}'
