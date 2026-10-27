from django.urls import path

from orders import views

app_name = 'orders'

urlpatterns = [
    path('', views.MyOrdersView.as_view(), name='list'),
    path('new/', views.NewOrderView.as_view(), name='new'),
    path('new/discard/', views.DiscardOrderView.as_view(), name='discard'),
    path('new/pharmacies/', views.ChoosePharmaciesView.as_view(), name='choose'),
    path('new/seal/<int:order_id>/', views.SealOrderView.as_view(), name='seal'),
]
