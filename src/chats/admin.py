from django.contrib import admin

from chats.models import Conversation, Message, UserMessage


def message_author_name(message):
    try:
        return message.usermessage.author_name
    except UserMessage.DoesNotExist:
        return ''


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('sender', 'author_name', 'body', 'created_at')
    readonly_fields = ('author_name', 'created_at')

    @admin.display(description='Autor')
    def author_name(self, message):
        return message_author_name(message)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('quote_request', 'updated_at', 'server_key_fingerprint')
    search_fields = (
        'quote_request__order__code',
        'quote_request__pharmacy__trade_name',
        'quote_request__order__client_account__user__email',
    )
    list_select_related = ('quote_request__order', 'quote_request__pharmacy')
    exclude = ('server_private_key',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = (MessageInline,)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'author_name', 'created_at')
    list_filter = ('sender',)
    search_fields = (
        'usermessage__author_name',
        'usermessage__author__email',
        'conversation__quote_request__order__code',
        'body',
    )
    list_select_related = ('conversation', 'usermessage')
    readonly_fields = ('author_name', 'created_at')
    ordering = ('-created_at',)

    @admin.display(description='Autor')
    def author_name(self, message):
        return message_author_name(message)
