from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from chats.commands.send_message import send_message
from chats.forms import CustomerMessageForm, MessageForm
from chats.models import Conversation
from chats.queries.customer_inbox import (
    get_customer_conversation,
    get_customer_inbox,
)
from chats.queries.pharmacy_inbox import get_conversation, get_pharmacy_inbox
from shared.views import RoleRequiredMixin


class PharmacyInboxMixin(RoleRequiredMixin):
    template_name = 'chats/inbox.html'
    partial_template_name = 'chats/_inbox_content.html'

    def allows(self, user):
        return user.is_pharmacy

    def conversation_id(self):
        return (
            self.kwargs.get('conversation_id')
            or self.request.GET.get('conversation_id')
            or self.request.GET.get('selected_id')
        )

    def show_chat_column(self):
        return True

    def get_template_names(self):
        if self.request.htmx:
            return [self.partial_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = self.request.GET.get('search', '').strip()
        filter_value = self.request.GET.get('filter', 'all')
        if filter_value not in {'all', 'unread'}:
            filter_value = 'all'

        user_id = self.request.user.id
        inbox = get_pharmacy_inbox(
            user_id,
            search,
            unread_only=filter_value == 'unread',
        )
        conversation_id = self.conversation_id()

        if conversation_id:
            try:
                selected = get_conversation(user_id, conversation_id)
            except Conversation.DoesNotExist:
                raise Http404 from None
        elif inbox.conversations:
            selected = get_conversation(user_id, inbox.conversations[0].id)
        else:
            selected = None

        context.update(
            conversations=inbox.conversations,
            selected=selected,
            search=search,
            filter=filter_value,
            form=context.get('form', MessageForm()),
            open_count=inbox.open_count,
            pending_count=inbox.pending_count,
            today_count=inbox.today_count,
            today=inbox.today,
            show_chat=self.show_chat_column(),
        )
        return context


class PharmacyInboxView(PharmacyInboxMixin, TemplateView):
    def show_chat_column(self):
        return self.conversation_id() is not None


class ConversationView(PharmacyInboxMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        if not request.htmx:
            return redirect('chats:inbox')
        return super().get(request, *args, **kwargs)


class SendMessageView(PharmacyInboxMixin, FormView):
    form_class = MessageForm
    http_method_names = ('post',)

    def form_valid(self, form):
        conversation_id = self.kwargs['conversation_id']
        send_message(
            self.request.user.id,
            conversation_id,
            form.cleaned_data['message'],
        )

        if not self.request.htmx:
            return redirect(
                f'{reverse("chats:inbox")}?conversation_id={conversation_id}'
            )

        return self.render_to_response(self.get_context_data(form=MessageForm()))


class CustomerInboxMixin(RoleRequiredMixin):
    template_name = 'chats/customer_inbox.html'
    partial_template_name = 'chats/_customer_chat.html'

    def allows(self, user):
        return user.is_customer

    def conversation_id(self):
        return self.kwargs.get('conversation_id') or self.request.GET.get(
            'conversation_id'
        )

    def get_template_names(self):
        if self.request.htmx:
            return [self.partial_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.user.id
        conversation_id = self.conversation_id()
        inbox = get_customer_inbox(user_id)
        conversations = inbox.conversations

        if conversation_id:
            try:
                selected = get_customer_conversation(user_id, conversation_id)
            except Conversation.DoesNotExist:
                raise Http404 from None
        elif conversations:
            selected = get_customer_conversation(user_id, conversations[0].id)
        else:
            selected = None

        context.update(
            conversations=conversations,
            selected=selected,
            form=context.get('form', CustomerMessageForm()),
        )
        return context


class CustomerInboxView(CustomerInboxMixin, TemplateView):
    pass


class CustomerReplyView(CustomerInboxMixin, FormView):
    form_class = CustomerMessageForm
    http_method_names = ('post',)

    def post(self, request, *args, **kwargs):
        try:
            get_customer_conversation(
                request.user.id,
                kwargs['conversation_id'],
            )
        except Conversation.DoesNotExist:
            raise Http404 from None

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        conversation_id = self.kwargs['conversation_id']
        send_message(
            self.request.user.id,
            conversation_id,
            form.cleaned_data['message'],
        )

        if not self.request.htmx:
            return redirect(
                f'{reverse("chats:customer_inbox")}?conversation_id={conversation_id}'
            )

        return self.render_to_response(
            self.get_context_data(form=CustomerMessageForm())
        )
