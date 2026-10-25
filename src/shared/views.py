from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not self.allows(request.user):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.info(self.request, 'Iniciá sesión para continuar.')
        return super().handle_no_permission()
