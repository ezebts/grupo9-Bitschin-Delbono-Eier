from django.urls import path

from orders import views

app_name = 'orders'

urlpatterns = [
    path('new/', views.NewOrderView.as_view(), name='new'),
]
