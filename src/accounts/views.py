from allauth.account.utils import complete_signup, perform_login
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView

from accounts.commands.set_pharmacy_visibility import set_pharmacy_visibility
from accounts.commands.signup import signup_with_invitation
from accounts.commands.update_client_profile import update_client_profile
from accounts.commands.update_pharmacy_profile import update_pharmacy_profile
from accounts.exceptions import (
    InvalidInvitationLinkError,
    PharmacyCantBecomeVisible,
    PharmacyCantClearSearchData,
)
from accounts.forms.client_profile import ClientProfileForm
from accounts.forms.pharmacy_profile import PharmacyProfileForm
from accounts.forms.set_password import SetPasswordForm
from accounts.models import InvitationLink, User
from accounts.queries.client_profile import get_account_client_profile
from accounts.queries.pharmacy_profile import get_account_pharmacy_profile
from shared.views import RoleRequiredMixin


class InvitationSignupView(View):
    confirm_template_name = 'accounts/invitation_confirm.html'
    complete_account_template_name = 'accounts/invitation_complete_account.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            self.invitation = InvitationLink.from_value(
                request.GET.get('_invitation', ''),
            )
        except InvalidInvitationLinkError as error:
            messages.error(request, error.message)
            return redirect('account_signup')

        if request.user.is_authenticated:
            return redirect(self._destination())

        self.user = User.objects.filter(email__iexact=self.invitation.email).first()

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if self.user is None:
            return render(request, self.confirm_template_name, self._context())

        if not self._account_is_complete(self.user):
            return self._render_complete_account(SetPasswordForm(self.user))

        return self._redirect_to_login()

    def post(self, request):
        if self.user is None:
            return self._create_account()

        if not self._account_is_complete(self.user):
            return self._set_password(request.POST)

        return self._redirect_to_login()

    @staticmethod
    def _account_is_complete(user):
        return (
            user.has_usable_password()
            or user.socialaccount_set.filter(
                provider='google',
            ).exists()
        )

    def _context(self):
        return {'invitation': self.invitation}

    def _create_account(self):
        try:
            user = signup_with_invitation(self.invitation)
        except InvalidInvitationLinkError as error:
            messages.error(self.request, error.message)
            return redirect('account_signup')

        return complete_signup(
            self.request,
            user,
            None,
            self.invitation.next_url or None,
        )

    def _set_password(self, data):
        form = SetPasswordForm(self.user, data=data)

        if not form.is_valid():
            return self._render_complete_account(form)

        form.save()
        return perform_login(
            self.request,
            self.user,
            redirect_url=self.invitation.next_url or None,
        )

    def _render_complete_account(self, form):
        return render(
            self.request,
            self.complete_account_template_name,
            {**self._context(), 'form': form},
        )

    def _redirect_to_login(self):
        login_url = reverse('account_login')

        if not self.invitation.next_url:
            return redirect(login_url)

        return redirect_to_login(self.invitation.next_url, login_url)

    def _destination(self):
        return self.invitation.next_url or 'home'


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
