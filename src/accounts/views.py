from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from accounts.commands.set_pharmacy_visibility import set_pharmacy_visibility
from accounts.commands.update_client_profile import update_client_profile
from accounts.commands.update_pharmacy_profile import update_pharmacy_profile
from accounts.exceptions import (
    PharmacyCantBecomeVisible,
    PharmacyCantClearSearchData,
)
from accounts.forms.client_profile import ClientProfileForm
from accounts.forms.pharmacy_profile import PharmacyProfileForm
from accounts.queries.client_profile import get_account_client_profile
from accounts.queries.pharmacy_profile import get_account_pharmacy_profile
from shared.views import RoleRequiredMixin


class ClientProfileView(LoginRequiredMixin, FormView):
    form_class = ClientProfileForm
    template_name = 'accounts/client_profile.html'
    success_url = reverse_lazy('profile')

    def get_initial(self):
        profile = get_account_client_profile(self.request.user.id)
        return ClientProfileForm.initial_from(profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = get_account_client_profile(self.request.user.id)
        context['profile'] = profile
        return context

    def form_valid(self, form):
        update_client_profile(self.request.user.id, form.cleaned_params)
        messages.success(self.request, 'Guardamos los cambios.')

        return super().form_valid(form)


class PharmacyProfileView(LoginRequiredMixin, FormView):
    form_class = PharmacyProfileForm
    template_name = 'accounts/pharmacy_profile.html'
    success_url = reverse_lazy('profile')

    def get_initial(self):
        profile = get_account_pharmacy_profile(self.request.user.id)
        return PharmacyProfileForm.initial_from(profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = get_account_pharmacy_profile(self.request.user.id)
        context['profile'] = profile
        return context

    def form_valid(self, form):
        try:
            update_pharmacy_profile(self.request.user.id, form.cleaned_params)
        except PharmacyCantClearSearchData as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(self.request, 'Guardamos los cambios.')
        return super().form_valid(form)


class PharmacyVisibilityView(RoleRequiredMixin, View):
    http_method_names = ('post',)

    def allows(self, user):
        return user.is_pharmacy

    def post(self, request):
        visible = 'visible' in request.POST
        error = None
        try:
            set_pharmacy_visibility(request.user.id, visible=visible)
        except PharmacyCantBecomeVisible as exc:
            visible = False
            error = exc.message

        if request.htmx:
            return render(
                request,
                'accounts/_visibility.html',
                {'visible': visible, 'error': error},
            )

        if error:
            messages.error(request, error)
        return redirect('profile')


class ProfileView(LoginRequiredMixin, View):
    client_view = ClientProfileView.as_view()
    pharmacy_view = PharmacyProfileView.as_view()

    @classmethod
    def view_for(cls, request, *args, **kwargs):
        view = cls.pharmacy_view if request.user.is_pharmacy else cls.client_view
        return view(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.view_for(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.view_for(request, *args, **kwargs)
