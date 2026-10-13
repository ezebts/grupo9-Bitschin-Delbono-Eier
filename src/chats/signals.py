from functools import partial

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from chats.commands.send_notice_mail import (
    send_client_reply_notice,
    send_order_status_notice,
    send_pharmacy_reply_notice,
    send_quote_decision_notice,
)
from chats.commands.send_quote_request_mail import send_quote_request_mail
from chats.commands.send_system_message import send_system_message
from chats.commands.start_conversation import start_conversation
from chats.models import Message, UserMessage
from orders.models import (
    FulfillmentStatus,
    QuoteRequest,
    QuoteRequestStatus,
    StatusEvent,
)


@receiver(post_save, sender=QuoteRequest)
def open_conversation(sender, instance, created, **kwargs):  # noqa: ARG001

    if not created:
        return

    conversation_id = start_conversation(
        instance.order.client_account.user_id,
        instance.id,
    )

    send_system_message(conversation_id, _('La solicitud también llega por mail'))


@receiver(post_save, sender=QuoteRequest)
def email_quote_request(sender, instance, created, **kwargs):  # noqa: ARG001

    if not created:
        return

    transaction.on_commit(partial(send_quote_request_mail, instance.pk))


@receiver(post_save, sender=UserMessage)
def email_chat_reply(sender, instance, created, **kwargs):  # noqa: ARG001
    if not created:
        return

    if instance.sender == Message.Sender.PHARMACY:
        notice = partial(send_client_reply_notice, instance.conversation_id)
    else:
        notice = partial(send_pharmacy_reply_notice, instance.conversation_id)

    transaction.on_commit(notice)


@receiver(post_save, sender=QuoteRequest)
def email_quote_update(sender, instance, created, **kwargs):  # noqa: ARG001
    if created:
        return

    conversation_id = instance.conversation.pk
    status = instance.status

    if status == QuoteRequestStatus.QUOTED and _quote_was_sent(
        kwargs.get('update_fields'),
    ):
        transaction.on_commit(
            partial(send_client_reply_notice, conversation_id, quote=True),
        )
        return

    if status == QuoteRequestStatus.ACCEPTED:
        transaction.on_commit(
            partial(send_quote_decision_notice, conversation_id, accepted=True),
        )
        transaction.on_commit(
            partial(send_pharmacy_reply_notice, conversation_id, decision=True),
        )
        return

    if status == QuoteRequestStatus.REJECTED:
        transaction.on_commit(
            partial(send_quote_decision_notice, conversation_id, accepted=False),
        )
        transaction.on_commit(
            partial(send_pharmacy_reply_notice, conversation_id, decision=False),
        )


@receiver(post_save, sender=StatusEvent)
def email_order_status(sender, instance, created, **kwargs):  # noqa: ARG001
    if not created or instance.status == FulfillmentStatus.ACCEPTED:
        return

    order = instance.order
    conversation_id = order.quote_requests.get(
        status=QuoteRequestStatus.ACCEPTED,
    ).conversation.pk
    status_label = order.fulfillment_label(instance.status).lower()

    transaction.on_commit(
        partial(send_order_status_notice, conversation_id, status_label),
    )


def _quote_was_sent(update_fields):
    if update_fields is None:
        return True
    return bool({'status', 'quoted_at'} & set(update_fields))
