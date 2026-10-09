from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from chats.forms import CustomerMessageForm, InquiryForm, MessageForm
from chats.models import Conversation, Message


def _role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if request.user.role != role:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped_view

    return decorator


def _inbox_context(request, selected=None, form=None):
    conversations = Conversation.objects.prefetch_related('messages')
    search = request.GET.get('search', '').strip()
    filter_value = request.GET.get('filter', 'all')
    if filter_value not in {'all', 'unread'}:
        filter_value = 'all'

    if search:
        conversations = conversations.filter(
            Q(customer_name__icontains=search)
            | Q(customer_email__icontains=search)
            | Q(subject__icontains=search)
            | Q(messages__body__icontains=search),
        ).distinct()
    if filter_value == 'unread':
        conversations = conversations.filter(waiting_for_pharmacy=True)

    return {
        'conversations': conversations,
        'selected': selected,
        'search': search,
        'filter': filter_value,
        'form': form or MessageForm(),
        'open_count': Conversation.objects.count(),
        'pending_count': Conversation.objects.filter(waiting_for_pharmacy=True).count(),
        'today_count': Conversation.objects.filter(
            created_at__date=timezone.localdate()
        ).count(),
        'today': timezone.localdate(),
    }


def _render_inbox(request, *, selected=None, form=None, show_chat=False):
    context = _inbox_context(request, selected=selected, form=form)
    context['show_chat'] = show_chat
    return render(request, 'chats/_inbox_content.html', context)


@require_http_methods(['GET'])
@_role_required('pharmacy')
def inbox(request):
    conversation_id = request.GET.get('conversation_id') or request.GET.get(
        'selected_id'
    )
    context = _inbox_context(request)
    conversations = context['conversations']
    selected = (
        get_object_or_404(conversations, pk=conversation_id)
        if conversation_id
        else conversations.first()
    )
    context['selected'] = selected
    if request.htmx:
        context['show_chat'] = conversation_id is not None
        return render(request, 'chats/_inbox_content.html', context)

    context['show_chat'] = conversation_id is not None
    return render(request, 'chats/inbox.html', context)


@require_http_methods(['GET'])
@_role_required('pharmacy')
def conversation(request, conversation_id):
    selected = get_object_or_404(
        Conversation.objects.prefetch_related('messages'),
        pk=conversation_id,
    )
    if not request.htmx:
        return redirect('chats:inbox')

    return _render_inbox(request, selected=selected, show_chat=True)


@require_POST
@_role_required('pharmacy')
def send_message(request, conversation_id):
    selected = get_object_or_404(Conversation, pk=conversation_id)
    form = MessageForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            Message.objects.create(
                conversation=selected,
                sender=Message.Sender.PHARMACY,
                body=form.cleaned_data['message'],
            )
            Conversation.objects.filter(pk=selected.pk).update(
                waiting_for_pharmacy=False,
                updated_at=timezone.now(),
            )
        selected.refresh_from_db()
        selected = Conversation.objects.prefetch_related('messages').get(pk=selected.pk)
        if not request.htmx:
            return redirect(f'{reverse("chats:inbox")}?conversation_id={selected.pk}')

    if not request.htmx:
        context = _inbox_context(request, selected=selected, form=form)
        context['show_chat'] = True
        return render(request, 'chats/inbox.html', context)

    return _render_inbox(
        request,
        selected=selected,
        form=MessageForm() if form.is_valid() else form,
        show_chat=True,
    )


@require_http_methods(['GET', 'POST'])
@_role_required('customer')
def new_inquiry(request):
    if request.method == 'POST':
        form = InquiryForm(request.POST)
        if form.is_valid():
            if not request.user.email:
                form.add_error(
                    None,
                    'Agregá un correo electrónico a tu cuenta '
                    'antes de enviar una consulta.',
                )
                return render(request, 'chats/new_inquiry.html', {'form': form})

            with transaction.atomic():
                conversation = Conversation.objects.create(
                    customer=request.user,
                    customer_name=request.user.get_full_name()
                    or request.user.get_username(),
                    customer_email=request.user.email,
                    customer_phone=form.cleaned_data['customer_phone'],
                    subject=form.cleaned_data['subject'],
                )
                Message.objects.create(
                    conversation=conversation,
                    sender=Message.Sender.CUSTOMER,
                    body=form.cleaned_data['message'],
                )
            return redirect(
                f'{reverse("chats:customer_inbox")}?conversation_id={conversation.pk}',
            )
    else:
        form = InquiryForm()

    return render(request, 'chats/new_inquiry.html', {'form': form})


@_role_required('customer')
@require_http_methods(['GET'])
def customer_inbox(request):
    conversations = Conversation.objects.filter(customer=request.user).prefetch_related(
        'messages'
    )
    conversation_id = request.GET.get('conversation_id')
    selected = (
        get_object_or_404(conversations, pk=conversation_id)
        if conversation_id
        else conversations.first()
    )

    return render(
        request,
        'chats/customer_inbox.html',
        {
            'conversations': conversations,
            'selected': selected,
            'form': CustomerMessageForm(),
        },
    )


@_role_required('customer')
@require_POST
def customer_reply(request, conversation_id):
    selected = get_object_or_404(
        Conversation.objects.filter(customer=request.user),
        pk=conversation_id,
    )
    form = CustomerMessageForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            Message.objects.create(
                conversation=selected,
                sender=Message.Sender.CUSTOMER,
                body=form.cleaned_data['message'],
            )
            Conversation.objects.filter(pk=selected.pk).update(
                waiting_for_pharmacy=True,
                updated_at=timezone.now(),
            )

        return redirect(
            f'{reverse("chats:customer_inbox")}?conversation_id={selected.pk}'
        )

    conversations = Conversation.objects.filter(customer=request.user).prefetch_related(
        'messages'
    )
    return render(
        request,
        'chats/customer_inbox.html',
        {
            'conversations': conversations,
            'selected': selected,
            'form': form,
        },
    )
