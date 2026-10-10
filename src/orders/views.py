from django.contrib import messages
from django.views.generic import FormView

from accounts.commands.update_client_location import update_client_location
from accounts.queries.client_profile import get_account_client_profile
from orders.forms import NewOrderForm
from shared.views import RoleRequiredMixin


class NewOrderView(RoleRequiredMixin, FormView):
    form_class = NewOrderForm
    template_name = 'orders/new_order.html'

    def allows(self, user):
        return user.is_customer

    def get_initial(self):
        profile = get_account_client_profile(self.request.user.id)
        return NewOrderForm.initial_from(profile.location)

    def form_valid(self, form):
        if 'save_draft' in self.request.POST:
            messages.info(self.request, 'Todavía no se pueden guardar borradores.')
        else:
            self._save_location(form.cleaned_data)
            messages.info(
                self.request,
                'Tu solicitud está completa. '
                'Elegir farmacias todavía no está disponible.',
            )
        return self.render_to_response(self.get_context_data(form=form))

    def _save_location(self, data):
        if not data['save_location']:
            return
        location = data.get('profile_location')
        if location is None:
            messages.warning(
                self.request,
                'Para guardarla en tu perfil, elegí una dirección con calle y altura.',
            )
            return
        update_client_location(self.request.user.id, location)
        messages.success(self.request, 'Guardamos la dirección en tu perfil.')
