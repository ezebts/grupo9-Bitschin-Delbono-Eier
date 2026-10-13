from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from chats.models import Conversation
from shared.urls import absolute_url

REPLY_INTERVAL = timedelta(minutes=15)
REPLY_NOTE = 'Te avisamos como máximo una vez cada 15 minutos por conversación.'


@transaction.atomic
def send_client_reply_notice(conversation_id, *, quote=False):
    """Emails the client that the pharmacy wrote or sent a quote."""

    conversation = _locked_conversation(conversation_id)
    preferences = conversation.quote_request.order.client_account.mail_preferences
    if preferences is None or not preferences.on_reply:
        return

    if _within_interval(conversation.client_notified_at):
        return

    pharmacy_name = conversation.quote_request.pharmacy.trade_name or 'La farmacia'
    order_code = conversation.quote_request.order.code
    if quote:
        subject = 'Recibiste un presupuesto'
        title = 'Recibiste un presupuesto'
        message = f'{pharmacy_name} envió un presupuesto para el pedido #{order_code}.'
    else:
        subject = 'La farmacia te escribió'
        title = 'La farmacia te escribió'
        message = f'{pharmacy_name} respondió en el pedido #{order_code}.'

    sent = _send(
        conversation.quote_request.order.client_account.user.email,
        subject,
        badge=f'Pedido · #{order_code}',
        title=title,
        message=message,
        action_url=_client_url(conversation),
        action_label='Ver conversación',
        note=REPLY_NOTE,
    )
    if not sent:
        return

    conversation.client_notified_at = timezone.now()
    conversation.save(update_fields=['client_notified_at'])


@transaction.atomic
def send_pharmacy_reply_notice(conversation_id, *, decision=None):
    """Emails the pharmacy that the client wrote or answered a quote."""

    conversation = _locked_conversation(conversation_id)
    pharmacy = conversation.quote_request.pharmacy
    preferences = pharmacy.mail_preferences
    if preferences is None or not preferences.on_reply:
        return

    if _within_interval(conversation.pharmacy_notified_at):
        return

    customer = _customer_name(conversation)
    order_code = conversation.quote_request.order.code
    if decision is True:
        subject = 'El cliente aceptó tu presupuesto'
        title = 'El cliente aceptó tu presupuesto'
        message = f'{customer} aceptó el presupuesto del pedido #{order_code}.'
    elif decision is False:
        subject = 'El cliente rechazó tu presupuesto'
        title = 'El cliente rechazó tu presupuesto'
        message = f'{customer} rechazó el presupuesto del pedido #{order_code}.'
    else:
        subject = 'El cliente te escribió'
        title = 'El cliente te escribió'
        message = f'{customer} envió un mensaje sobre el pedido #{order_code}.'

    sent = _send(
        pharmacy.request_email,
        subject,
        badge=f'Pedido · #{order_code}',
        title=title,
        message=message,
        action_url=_pharmacy_url(conversation),
        action_label='Ver conversación',
        note=REPLY_NOTE,
    )
    if not sent:
        return

    conversation.pharmacy_notified_at = timezone.now()
    conversation.save(update_fields=['pharmacy_notified_at'])


@transaction.atomic
def send_order_status_notice(conversation_id, status_label):
    """Emails the client that the order moved to a new status."""

    conversation = _locked_conversation(conversation_id)
    preferences = conversation.quote_request.order.client_account.mail_preferences
    if preferences is None or not preferences.on_status_change:
        return

    order_code = conversation.quote_request.order.code
    title = f'Tu pedido está {status_label}'
    _send(
        conversation.quote_request.order.client_account.user.email,
        title,
        badge=f'Pedido · #{order_code}',
        title=title,
        message=f'El pedido #{order_code} ahora está {status_label}.',
        action_url=_client_url(conversation),
        action_label='Ver pedido',
        note='',
    )


@transaction.atomic
def send_quote_decision_notice(conversation_id, *, accepted):
    """Emails the pharmacy that the client accepted or rejected the quote."""

    conversation = _locked_conversation(conversation_id)
    pharmacy = conversation.quote_request.pharmacy
    preferences = pharmacy.mail_preferences
    if preferences is not None and preferences.on_quote_status:
        customer = _customer_name(conversation)
        order_code = conversation.quote_request.order.code
        if accepted:
            subject = 'Aceptaron tu presupuesto'
            title = 'Aceptaron tu presupuesto'
            message = f'{customer} aceptó el presupuesto del pedido #{order_code}.'
        else:
            subject = 'Rechazaron tu presupuesto'
            title = 'Rechazaron tu presupuesto'
            message = f'{customer} rechazó el presupuesto del pedido #{order_code}.'

        _send(
            pharmacy.request_email,
            subject,
            badge=f'Pedido · #{order_code}',
            title=title,
            message=message,
            action_url=_pharmacy_url(conversation),
            action_label='Ver conversación',
            note='',
        )


def _locked_conversation(conversation_id):
    return (
        Conversation.objects.select_for_update()
        .select_related(
            'quote_request__order__client_account__user',
            'quote_request__pharmacy',
        )
        .get(pk=conversation_id)
    )


def _within_interval(notified_at):
    if notified_at is None:
        return False
    return timezone.now() - notified_at < REPLY_INTERVAL


def _customer_name(conversation):
    user = conversation.quote_request.order.client_account.user
    full_name = f'{user.first_name} {user.last_name}'.strip()
    return full_name or user.email


def _client_url(conversation):
    inbox = reverse('chats:customer_inbox')
    order_id = conversation.quote_request.order_id
    return absolute_url(
        f'{inbox}?order_id={order_id}&conversation_id={conversation.pk}',
    )


def _pharmacy_url(conversation):
    inbox = reverse('chats:inbox')
    return absolute_url(f'{inbox}?conversation_id={conversation.pk}')


def _send(recipient, subject, **context):
    if not (recipient or '').strip():
        return False

    message = EmailMessage(
        subject=subject,
        body=render_to_string('chats/mail/notice.html', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.content_subtype = 'html'
    message.send(using='default')
    return True
