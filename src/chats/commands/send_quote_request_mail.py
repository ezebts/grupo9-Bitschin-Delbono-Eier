from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.models import InvitationLink, User
from chats.models import Conversation
from orders.models import DeliveryPreference, QuoteRequest, Urgency
from shared.urls import absolute_url

PREPARATION_PREVIEW_LENGTH = 80


def send_quote_request_mail(quote_request_id):
    """Emails the pharmacy that a client asked them for a quote."""

    quote_request = QuoteRequest.objects.select_related(
        'pharmacy',
        'order__client_account__user',
    ).get(pk=quote_request_id)

    order = quote_request.order
    pharmacy = quote_request.pharmacy
    if not pharmacy.request_email.strip():
        return

    next_url = _next_url(quote_request)

    if pharmacy.accounts.exists():
        action_url = absolute_url(next_url)
    else:
        action_url = absolute_url(
            str(
                InvitationLink(
                    role=User.Role.PHARMACY,
                    email=pharmacy.request_email,
                    next_url=next_url,
                    details={'pharmacy_id': pharmacy.pk},
                )
            )
        )

    context = {
        'pharmacy_name': pharmacy.trade_name,
        'order_code': order.code,
        'customer_name': _customer_name(order.client_account.user),
        'preparation': _preparation(order.formula),
        'presentation': order.presentation,
        'urgency': Urgency(order.urgency).label,
        'delivery': _delivery_label(order),
        'action_url': action_url,
    }

    message = EmailMessage(
        subject='Nueva solicitud de presupuesto',
        body=render_to_string('chats/mail/new_quote_request.html', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[pharmacy.request_email],
    )

    message.content_subtype = 'html'
    message.send(using='default')


def _customer_name(user):
    full_name = f'{user.first_name} {user.last_name}'.strip()
    return full_name or user.email


def _preparation(formula):
    compact = ' '.join(formula.split())
    if len(compact) <= PREPARATION_PREVIEW_LENGTH:
        return compact
    return f'{compact[: PREPARATION_PREVIEW_LENGTH - 3]}...'


def _delivery_label(order):
    return ', '.join(
        str(DeliveryPreference(value).label) for value in order.delivery_preferences
    )


def _next_url(quote_request):
    inbox = reverse('chats:inbox')
    try:
        conversation_id = quote_request.conversation.id
    except Conversation.DoesNotExist:
        return inbox
    return f'{inbox}?conversation_id={conversation_id}'
