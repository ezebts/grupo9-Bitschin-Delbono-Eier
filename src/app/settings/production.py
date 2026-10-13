from urllib.parse import unquote, urlparse

from decouple import config

from .base import *

DEBUG = False

ALLOWED_HOSTS.append('.recetasmagistral.com.ar')
CSRF_TRUSTED_ORIGINS = [
    f'https://{HOST}',
    'https://recetasmagistral.com.ar',
    'https://www.recetasmagistral.com.ar',
]
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True

DATABASE_URL = config('DATABASE_URL')
DATABASE = urlparse(DATABASE_URL)

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': DATABASE.path.lstrip('/'),
        'USER': unquote(DATABASE.username or ''),
        'PASSWORD': unquote(DATABASE.password or ''),
        'HOST': DATABASE.hostname or '',
        'PORT': str(DATABASE.port or ''),
        'OPTIONS': {'sslmode': 'require'},
    },
}

DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL',
    default='Magistral <hola@notificaciones.recetasmagistral.com.ar>',
)

INSTALLED_APPS = [*INSTALLED_APPS, 'anymail']

RESEND_API_KEY = config('RESEND_API_KEY', default='')

MAILERS = {
    'default': {
        'BACKEND': 'anymail.backends.resend.EmailBackend',
        'OPTIONS': {
            'api_key': RESEND_API_KEY,
        },
    },
}

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STORAGES = {
    **STORAGES,
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
