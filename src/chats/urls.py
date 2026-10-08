from django.urls import path

from chats import views

app_name = 'chats'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('new/', views.new_inquiry, name='new_inquiry'),
    path('my/', views.customer_inbox, name='customer_inbox'),
    path(
        'my/<int:conversation_id>/messages/',
        views.customer_reply,
        name='customer_reply',
    ),
    path(
        'conversations/<int:conversation_id>/', views.conversation, name='conversation'
    ),
    path(
        'conversations/<int:conversation_id>/messages/',
        views.send_message,
        name='send_message',
    ),
]
