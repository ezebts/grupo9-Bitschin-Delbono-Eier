from django import template
from django.urls import reverse

from accounts.queries.device_keys import get_user_device_keys

register = template.Library()


@register.inclusion_tag('accounts/_account_security.html')
def account_security(user):
    return {
        'account_security': {
            'register_device_url': reverse('register_device'),
            'fingerprints': [
                device_key.fingerprint for device_key in get_user_device_keys(user.id)
            ],
        },
    }
