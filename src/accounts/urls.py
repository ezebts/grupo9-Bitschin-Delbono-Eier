from django.urls import path

from accounts import views

urlpatterns = [
    path('invitation/', views.InvitationSignupView.as_view(), name='invitation'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path(
        'profile/visibility/',
        views.PharmacyVisibilityView.as_view(),
        name='pharmacy_visibility',
    ),
    path('device-keys/', views.DeviceKeyView.as_view(), name='device_keys'),
]
