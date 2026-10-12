from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from chats.commands.send_message import send_message
from chats.forms import CustomerMessageForm, MessageForm, QuoteForm
from chats.models import Conversation
from chats.queries.customer_inbox import (
    get_customer_conversation,
    get_customer_inbox,
)
from chats.queries.pharmacy_inbox import get_conversation, get_pharmacy_inbox
from orders.commands.save_quote import save_quote
from orders.commands.withdraw_quote import withdraw_quote
from orders.models import Order, QuoteRequestStatus
from shared.exceptions import Error
from shared.views import RoleRequiredMixin


class PharmacyInboxMixin(RoleRequiredMixin):
    template_name = 'chats/inbox.html'
    partial_template_name = 'chats/_inbox_content.html'

    def allows(self, user):
        return user.is_pharmacy

    def conversation_id(self):
        return self.kwargs.get('conversation_id') or self.request.GET.get(
            'conversation_id'
        )

    def get_selected_conversation(self, conversation_id):
        try:
            return get_conversation(self.request.user.id, conversation_id)
        except Conversation.DoesNotExist:
            raise Http404 from None

    @staticmethod
    def quote_initial(selected):
        if selected.quote_status != QuoteRequestStatus.QUOTED:
            return {
                'delivery_preferences': selected.delivery_options,
                'delivery_cost': 0,
            }

        return {
            'price': selected.quote_price,
            'preparation_time': selected.preparation_time,
            'delivery_preferences': selected.delivery_preferences,
            'delivery_cost': selected.delivery_cost,
            'valid_until': selected.valid_until,
        }

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
            selected = self.get_selected_conversation(conversation_id)
        elif inbox.conversations:
            selected = get_conversation(user_id, inbox.conversations[0].id)
        else:
            selected = None

        quote_form = context.get('quote_form')
        if quote_form is None:
            quote_form = (
                QuoteForm(
                    initial=self.quote_initial(selected),
                    delivery_options=selected.delivery_options,
                )
                if selected
                else QuoteForm()
            )

        context.update(
            conversations=inbox.conversations,
            selected=selected,
            search=search,
            filter=filter_value,
            form=context.get('form', MessageForm()),
            quote_form=quote_form,
            quote_error=context.get('quote_error', ''),
            open_count=inbox.open_count,
            pending_count=inbox.pending_count,
        )
        return context


class PharmacyInboxView(PharmacyInboxMixin, TemplateView):
    pass


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


class SaveQuoteView(PharmacyInboxMixin, FormView):
    form_class = QuoteForm
    http_method_names = ('post',)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        selected = self.get_selected_conversation(self.kwargs['conversation_id'])
        kwargs['delivery_options'] = selected.delivery_options
        kwargs['initial'] = self.quote_initial(selected)
        return kwargs

    def get_context_data(self, **kwargs):
        quote_form = kwargs.pop('form', None)
        context = super().get_context_data(**kwargs)
        if quote_form is not None:
            context['quote_form'] = quote_form
        return context

    def form_valid(self, form):
        try:
            save_quote(
                self.request.user.id,
                self.kwargs['conversation_id'],
                form.cleaned_params,
            )
        except Error as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        if not self.request.htmx:
            return redirect(self.inbox_url())

        return self.render_to_response(self.get_context_data())

    def inbox_url(self):
        query = self.request.GET.copy()
        query['conversation_id'] = self.kwargs['conversation_id']
        return f'{reverse("chats:inbox")}?{query.urlencode()}'


class WithdrawQuoteView(PharmacyInboxMixin, TemplateView):
    http_method_names = ('post',)

    def post(self, request, conversation_id):
        self.get_selected_conversation(conversation_id)
        quote_error = ''

        try:
            withdraw_quote(request.user.id, conversation_id)
        except Error as error:
            quote_error = error.message

        if not request.htmx:
            if quote_error:
                return self.render_to_response(
                    self.get_context_data(quote_error=quote_error),
                )
            query = request.GET.copy()
            query['conversation_id'] = conversation_id
            return redirect(f'{reverse("chats:inbox")}?{query.urlencode()}')

        return self.render_to_response(
            self.get_context_data(quote_error=quote_error),
        )


class CustomerInboxMixin(RoleRequiredMixin):
    template_name = 'chats/customer_inbox.html'
    partial_template_name = 'chats/_customer_chat.html'

    def allows(self, user):
        return user.is_customer

    def conversation_id(self):
        return self.kwargs.get('conversation_id') or self.request.GET.get(
            'conversation_id'
        )

    def order_id(self):
        order_id = self.request.GET.get('order_id')
        if not order_id or not order_id.isdigit():
            raise Http404
        return int(order_id)

    def get_template_names(self):
        if self.request.htmx:
            return [self.partial_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.user.id
        conversation_id = self.conversation_id()
        order_id = self.order_id()
        try:
            inbox = get_customer_inbox(user_id, order_id)
        except Order.DoesNotExist:
            raise Http404 from None
        conversations = inbox.conversations

        if not conversation_id and conversations:
            conversation_id = conversations[0].id

        if conversation_id:
            try:
                selected = get_customer_conversation(
                    user_id,
                    order_id,
                    conversation_id,
                )
            except Conversation.DoesNotExist:
                raise Http404 from None
        else:
            selected = None

        context.update(
            conversations=conversations,
            selected=selected,
            order_code=inbox.code,
            order_progress=inbox.progress_label,
            preparation_label=inbox.preparation_label,
            presentation=inbox.presentation,
            urgency_label=inbox.urgency_label,
            delivery_label=inbox.delivery_label,
            sent_at=inbox.created_at,
            prescription_name=inbox.prescription_name,
            prescription_url=inbox.prescription_url,
            order_id=order_id,
            form=context.get('form', CustomerMessageForm()),
        )
        return context


class CustomerInboxView(CustomerInboxMixin, TemplateView):
    pass


class CustomerReplyView(CustomerInboxMixin, FormView):
    form_class = CustomerMessageForm
    http_method_names = ('post',)

    def form_valid(self, form):
        conversation_id = self.kwargs['conversation_id']
        send_message(
            self.request.user.id,
            conversation_id,
            form.cleaned_data['message'],
        )

        if not self.request.htmx:
            url = f'{reverse("chats:customer_inbox")}?conversation_id={conversation_id}'
            order_id = self.request.GET.get('order_id')
            if order_id:
                url = f'{url}&order_id={order_id}'
            return redirect(url)

        return self.render_to_response(
            self.get_context_data(form=CustomerMessageForm())
        )
