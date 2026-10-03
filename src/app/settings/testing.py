from .base import *

DEBUG = True

SECRET_KEY = 'test-insecure-secret-key'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
    },
}

STORAGES = {
    **STORAGES,
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
