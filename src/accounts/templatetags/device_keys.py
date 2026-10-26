from django import template
from django.urls import reverse

from accounts.queries.device_keys import get_user_device_keys

register = template.Library()


@register.inclusion_tag('accounts/_encryption_account.html')
def encryption_account(user):
    return {
        'encryption_account': {
            'register_url': reverse('device_keys'),
            'fingerprints': [
                device_key.fingerprint for device_key in get_user_device_keys(user.id)
            ],
        },
    }
