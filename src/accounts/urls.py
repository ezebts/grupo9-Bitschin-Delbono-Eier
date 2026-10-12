from django.urls import path

from accounts import views

urlpatterns = [
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path(
        'profile/visibility/',
        views.PharmacyVisibilityView.as_view(),
        name='pharmacy_visibility',
    ),
]
