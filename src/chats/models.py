from django.conf import settings
from django.db import models


class Conversation(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='chat_conversations',
        blank=True,
        null=True,
    )
    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=200)
    waiting_for_pharmacy = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.subject} — {self.customer_name}'

    @property
    def initials(self):
        return ''.join(part[0] for part in self.customer_name.split()[:2]).upper()

    @property
    def color(self):
        return ('lavender', 'coral', 'blue', 'gold', 'sage')[self.pk % 5]

    @property
    def last_message(self):
        messages = list(self.messages.all())
        return messages[-1] if messages else None


class Message(models.Model):
    class Sender(models.TextChoices):
        CUSTOMER = 'customer', 'Cliente'
        PHARMACY = 'pharmacy', 'Farmacia'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.CharField(max_length=10, choices=Sender.choices)
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']

    def __str__(self):
        return f'{self.get_sender_display()}: {self.body[:50]}'
