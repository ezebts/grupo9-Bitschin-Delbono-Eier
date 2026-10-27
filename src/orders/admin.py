from django.contrib import admin

from chats.models import Conversation
from orders.models import Order, QuoteRequest, StatusEvent

_MONEY_LABELS = {
    '_price': 'Precio',
    '_delivery_cost': 'Costo de envío',
    '_delivery_preferences': 'Entrega',
}


def money_label(money):
    if money is None:
        return ''
    return f'{money.currency} {money.amount}'


class QuoteRequestInline(admin.TabularInline):
    model = QuoteRequest
    extra = 0
    fields = (
        'pharmacy',
        'status',
        'price',
        'preparation_time',
        'valid_until',
        'quoted_at',
        'created_at',
    )
    readonly_fields = ('price', 'created_at')
    show_change_link = True

    @admin.display(description='Precio')
    def price(self, quote_request):
        return money_label(quote_request.price)


class StatusEventInline(admin.TabularInline):
    model = StatusEvent
    extra = 0
    fields = ('status', 'estimated_at', 'created_at')
    readonly_fields = ('created_at',)


class ConversationInline(admin.StackedInline):
    model = Conversation
    extra = 0
    max_num = 1
    show_change_link = True
    exclude = ('server_private_key',)
    readonly_fields = ('created_at', 'updated_at')


class MoneyFieldLabelsMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        label = _MONEY_LABELS.get(db_field.name)
        if label:
            kwargs['label'] = label
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Order)
class OrderAdmin(MoneyFieldLabelsMixin, admin.ModelAdmin):
    list_display = (
        'code',
        'client_account',
        'preparation_tag',
        'urgency',
        'created_at',
    )
    list_filter = ('urgency', 'preparation_tag')
    search_fields = (
        'code',
        'client_account__user__email',
        'client_account__user__first_name',
        'client_account__user__last_name',
    )
    list_select_related = ('client_account__user',)
    readonly_fields = ('created_at',)
    inlines = (QuoteRequestInline, StatusEventInline)


@admin.register(QuoteRequest)
class QuoteRequestAdmin(MoneyFieldLabelsMixin, admin.ModelAdmin):
    list_display = (
        'order',
        'pharmacy',
        'status',
        'price',
        'preparation_time',
        'valid_until',
    )
    list_filter = ('status',)
    search_fields = ('order__code', 'pharmacy__trade_name', 'pharmacy__request_email')
    list_select_related = ('order', 'pharmacy')
    readonly_fields = ('price', 'delivery_cost', 'created_at')
    inlines = (ConversationInline,)

    @admin.display(description='Precio')
    def price(self, quote_request):
        return money_label(quote_request.price)

    @admin.display(description='Costo de envío')
    def delivery_cost(self, quote_request):
        return money_label(quote_request.delivery_cost)
