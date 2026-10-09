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
        'conversations/<int:conversation_id>/',
        views.ConversationView.as_view(),
        name='conversation',
    ),
    path(
        'conversations/<int:conversation_id>/messages/',
        views.SendMessageView.as_view(),
        name='send_message',
    ),
]
