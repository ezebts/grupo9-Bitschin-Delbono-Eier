from django.db.models.signals import post_save
from django.dispatch import receiver

from chats.commands.start_conversation import start_conversation
from orders.models import QuoteRequest


@receiver(post_save, sender=QuoteRequest)
def open_conversation(sender, instance, created, **kwargs):  # noqa: ARG001
    if not created:
        return
    start_conversation(instance.order.client_account.user_id, instance.pk)
