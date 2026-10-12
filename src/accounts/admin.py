from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Pharmacy, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = (*UserAdmin.fieldsets, ('Rol', {'fields': ('role',)}))
    list_display = (*UserAdmin.list_display, 'role')
    list_filter = (*UserAdmin.list_filter, 'role')


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    exclude = ('coordinates',)
    list_display = ('trade_name', 'kind', 'visible', 'request_email')
    list_filter = ('visible', 'kind')
    search_fields = ('trade_name', 'request_email')
