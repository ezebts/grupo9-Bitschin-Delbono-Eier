from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView, View

from chats.commands.send_message import send_message
from chats.forms import ChatQuoteForm, CustomerMessageForm, MessageForm
from chats.models import Conversation
from chats.queries.customer_inbox import (
    get_customer_conversation,
    get_customer_inbox,
)
from chats.queries.pharmacy_inbox import get_conversation, get_pharmacy_inbox
from orders.commands.accept_quote import accept_quote
from orders.commands.reject_quote import reject_quote
from orders.commands.submit_quote import submit_quote
from orders.commands.withdraw_quote import withdraw_quote
from orders.models import Order, QuoteRequest, QuoteRequestStatus
from shared.exceptions import Error
from shared.views import RoleRequiredMixin


class PharmacyInboxMixin(RoleRequiredMixin):
    template_name = 'chats/inbox.html'
    partial_template_name = 'chats/_inbox_content.html'
    inbox_filters = (
        QuoteRequestStatus.WAITING,
        QuoteRequestStatus.QUOTED,
        QuoteRequestStatus.ACCEPTED,
    )

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
                'price_currency': selected.quote_currency,
                'delivery_cost_currency': selected.delivery_cost_currency,
                'delivery_preferences': selected.delivery_options,
            }

        return {
            'price_currency': selected.quote_currency,
            'delivery_cost_currency': selected.delivery_cost_currency,
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
        raw_filter = self.request.GET.get('filter')
        if raw_filter:
            filter_value = QuoteRequestStatus(raw_filter)
        else:
            filter_value = QuoteRequestStatus.WAITING

        user_id = self.request.user.id
        inbox = get_pharmacy_inbox(
            user_id,
            search,
            quote_filter=filter_value,
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
                ChatQuoteForm(
                    initial=self.quote_initial(selected),
                    delivery_options=selected.delivery_options,
                )
                if selected
                else ChatQuoteForm()
            )

        message_form = context.get('form')
        if not isinstance(message_form, MessageForm):
            message_form = MessageForm()

        context.update(
            conversations=inbox.conversations,
            selected=selected,
            search=search,
            filter=filter_value,
            inbox_filters=self.inbox_filters,
            form=message_form,
            quote_form=quote_form,
            quote_error=context.get('quote_error', ''),
            waiting_count=inbox.waiting_count,
            quoted_count=inbox.quoted_count,
            accepted_count=inbox.accepted_count,
        )
        return context

    def render_inbox_after_quote_action(self):
        conversation_id = self.conversation_id()
        if not conversation_id:
            raise Http404

        selected = self.get_selected_conversation(conversation_id)
        query = self.request.GET.copy()
        query['conversation_id'] = conversation_id
        query['filter'] = QuoteRequestStatus(selected.quote_status).value

        if not self.request.htmx:
            return redirect(f'{reverse("chats:inbox")}?{query.urlencode()}')

        self.request.GET = query
        return self.render_to_response(self.get_context_data())


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


class ChatSaveQuoteView(PharmacyInboxMixin, FormView):
    form_class = ChatQuoteForm
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
            submit_quote(
                self.request.user.id,
                self.kwargs['conversation_id'],
                form.cleaned_params,
            )
        except Error as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        return self.render_inbox_after_quote_action()


class WithdrawQuoteView(PharmacyInboxMixin, TemplateView):
    http_method_names = ('post',)

    def post(self, request, conversation_id):
        self.get_selected_conversation(conversation_id)
        quote_error = ''

        try:
            withdraw_quote(request.user.id, conversation_id)
        except Error as error:
            quote_error = error.message

        if quote_error:
            if not request.htmx:
                return self.render_to_response(
                    self.get_context_data(quote_error=quote_error),
                )
            return self.render_to_response(
                self.get_context_data(quote_error=quote_error),
            )

        return self.render_inbox_after_quote_action()


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


class CustomerQuoteAnswerView(RoleRequiredMixin, View):
    http_method_names = ('post',)

    def allows(self, user):
        return user.is_customer

    def answer(self, conversation_id):
        raise NotImplementedError

    def post(self, request, conversation_id):
        order_id = request.GET.get('order_id', '')
        if not order_id.isdigit():
            raise Http404

        try:
            self.answer(conversation_id)
        except QuoteRequest.DoesNotExist:
            raise Http404 from None
        except Error as error:
            messages.error(request, error.message)

        url = (
            f'{reverse("chats:customer_inbox")}'
            f'?order_id={order_id}&conversation_id={conversation_id}'
        )

        if request.htmx:
            return HttpResponse(headers={'HX-Redirect': url})

        return redirect(url)


class AcceptQuoteView(CustomerQuoteAnswerView):
    def answer(self, conversation_id):
        accept_quote(self.request.user.id, conversation_id)


class RejectQuoteView(CustomerQuoteAnswerView):
    def answer(self, conversation_id):
        reject_quote(self.request.user.id, conversation_id)
