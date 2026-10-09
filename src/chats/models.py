from dataclasses import dataclass

from django.conf import settings
from django.db import models
from django.db.models import OuterRef, Q, Subquery


@dataclass(frozen=True)
class MessageAuthor:
    user_id: int
    display_name: str


class ConversationQuerySet(models.QuerySet):
    def with_customer(self):
        return self.select_related('customer')

    def with_messages(self):
        return self.prefetch_related('messages')

    def for_customer(self, user_id):
        return self.filter(customer_id=user_id)

    def for_pharmacy(self, user_id):
        return self.filter(pharmacy_id=user_id)

    def pending(self):
        latest_sender = (
            Message.objects.filter(conversation=OuterRef('pk'))
            .exclude(sender=Message.Sender.SYSTEM)
            .order_by('-created_at', '-pk')
            .values('sender')[:1]
        )
        return self.alias(latest_sender=Subquery(latest_sender)).filter(
            Q(latest_sender=Message.Sender.CUSTOMER) | Q(latest_sender__isnull=True)
        )

    def search(self, term):
        return self.filter(
            Q(customer__first_name__icontains=term)
            | Q(customer__last_name__icontains=term)
            | Q(customer__email__icontains=term)
            | Q(title__icontains=term)
            | Q(messages__body__icontains=term),
        ).distinct()


class Conversation(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='chat_conversations',
        blank=True,
        null=True,
    )

    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='pharmacy_conversations',
        blank=True,
        null=True,
    )

    title = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        ordering = ('-updated_at',)

    def __str__(self):
        return self.title or f'Conversación {self.pk}'

    def send_message(self, user_id, display_name, text):
        if user_id == self.customer_id:
            sender = Message.Sender.CUSTOMER
        else:
            sender = Message.Sender.PHARMACY

        return UserMessage(
            conversation=self,
            author_id=user_id,
            author_name=display_name,
            body=text,
            sender=sender,
        )

    def send_system_message(self, text):
        return Message(
            conversation=self,
            body=text,
            sender=Message.Sender.SYSTEM,
        )


class Message(models.Model):
    class Sender(models.TextChoices):
        CUSTOMER = 'customer'
        PHARMACY = 'pharmacy'
        SYSTEM = 'system'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )

    body = models.TextField(max_length=2000)

    sender = models.CharField(max_length=8, choices=Sender.choices)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')

    def __str__(self):
        return self.body[:50]

    @property
    def is_customer(self):
        return self.sender == self.Sender.CUSTOMER

    @property
    def is_pharmacy(self):
        return self.sender == self.Sender.PHARMACY

    @property
    def is_system(self):
        return self.sender == self.Sender.SYSTEM


class UserMessage(Message):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='chat_messages',
    )

    author_name = models.CharField(max_length=150)

    def __str__(self):
        return f'{self.author_name}: {self.body[:50]}'

    @property
    def message_author(self):
        return MessageAuthor(self.author_id, self.author_name)
