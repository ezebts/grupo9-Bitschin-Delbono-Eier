"""Shared Django settings.

Select an environment module, not this one:

- ``app.settings.development`` for local work
- ``app.settings.production`` for deployment
- ``app.settings.testing`` for pytest

Set ``DJANGO_SETTINGS_MODULE`` to choose. ``manage.py`` defaults to development.
``asgi.py`` defaults to production.
"""

from pathlib import Path

from decouple import Csv, config

SECRET_KEY = config('SECRET_KEY')

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'heroicons',
    'django_htmx',
    'django_tailwind_cli',
    'django_tasks_db',
    'widget_tweaks',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'shared',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'app.urls'

ASGI_APPLICATION = 'app.asgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='postgres'),
        'USER': config('POSTGRES_USER', default='postgres'),
        'PASSWORD': config('POSTGRES_PASSWORD', default='postgres'),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}


# Authentication

AUTHENTICATION_BACKENDS = [
    'allauth.account.auth_backends.AuthenticationBackend',
]


# Authentication - Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'es-ar'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images) & Media files (Users/System generated)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

TAILWIND_CLI_USE_DAISY_UI = True
TAILWIND_CLI_DIST_CSS = 'shared/css/tailwind.css'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR.parent / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'shared/static_tailwind'] # Extra static dirs
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR.parent / 'media'
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
}


# Background Tasks

TASKS = {
    'default': {
        'BACKEND': 'django_tasks_db.DatabaseBackend',
    },
}


# Logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "app": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}
