from django.conf import settings
from django.db import models

from shared.encryption import fingerprint_public_key


class DeviceKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_keys',
    )
    public_key = models.TextField()
    fingerprint = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')

    def __str__(self):
        return f'{self.user_id}:{self.fingerprint}'

    def save(self, *args, **kwargs):
        self.fingerprint = fingerprint_public_key(self.public_key)
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'fingerprint'}
        super().save(*args, **kwargs)
