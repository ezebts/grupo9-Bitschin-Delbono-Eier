from django.urls import path

from chats import views

app_name = 'chats'

urlpatterns = [
    path('', views.PharmacyInboxView.as_view(), name='inbox'),
    path('my/', views.CustomerInboxView.as_view(), name='customer_inbox'),
    path(
        'my/<int:conversation_id>/messages/',
        views.CustomerReplyView.as_view(),
        name='customer_reply',
    ),
    path(
        'my/<int:conversation_id>/quote/accept/',
        views.AcceptQuoteView.as_view(),
        name='accept_quote',
    ),
    path(
        'my/<int:conversation_id>/quote/reject/',
        views.RejectQuoteView.as_view(),
        name='reject_quote',
    ),
    path(
        'my/<int:conversation_id>/review/',
        views.CustomerReviewView.as_view(),
        name='customer_review',
    ),
    path(
        'conversations/<int:conversation_id>/messages/',
        views.SendMessageView.as_view(),
        name='send_message',
    ),
    path(
        'conversations/<int:conversation_id>/quote/',
        views.ChatSaveQuoteView.as_view(),
        name='save_quote',
    ),
    path(
        'conversations/<int:conversation_id>/quote/withdraw/',
        views.WithdrawQuoteView.as_view(),
        name='withdraw_quote',
    ),
    path(
        'conversations/<int:conversation_id>/order/advance/',
        views.AdvanceOrderView.as_view(),
        name='advance_order',
    ),
]
