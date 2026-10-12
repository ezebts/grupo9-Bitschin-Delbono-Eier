from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, TemplateView, View

from accounts.models import PreparationTag, SearchRadius
from accounts.queries.client_profile import get_account_client_profile
from accounts.queries.find_nearby_pharmacies import find_nearby_pharmacies
from orders.forms import NewOrderForm
from shared.values import Coordinates
from shared.views import RoleRequiredMixin


class NewOrderView(RoleRequiredMixin, FormView):
    form_class = NewOrderForm
    template_name = 'orders/new_order.html'

    def allows(self, user):
        return user.is_customer

    def get_initial(self):
        profile = get_account_client_profile(self.request.user.id)
        initial = NewOrderForm.initial_from(profile.location)
        if 'volver' not in self.request.GET:
            return initial
        saved = self.request.session.get(ChoosePharmaciesView.order_session_key)
        if not saved:
            return initial
        fields = (
            'preparation_tag',
            'presentation',
            'formula',
            'urgency',
            'delivery_preferences',
            'search_area',
            'latitude',
            'longitude',
            'address',
            'locality',
            'postal_code',
            'note',
        )
        initial.update({field: saved[field] for field in fields if field in saved})
        return initial

    def form_valid(self, form):
        params = form.cleaned_params
        data = form.cleaned_data
        self.request.session[ChoosePharmaciesView.order_session_key] = {
            'preparation_tag': params.preparation_tag.value,
            'presentation': params.presentation,
            'formula': params.formula,
            'urgency': params.urgency,
            'delivery_preferences': list(params.delivery_preferences),
            'search_area': params.search_area,
            'latitude': params.search_coordinates.latitude,
            'longitude': params.search_coordinates.longitude,
            'address': data.get('address') or '',
            'locality': data.get('locality') or '',
            'postal_code': data.get('postal_code') or '',
            'note': params.note,
            'has_prescription': params.prescription_file is not None,
        }

        return redirect('orders:choose')


class DiscardOrderView(RoleRequiredMixin, View):
    http_method_names = ('post',)

    def allows(self, user):
        return user.is_customer

    def post(self, request):
        request.session.pop(ChoosePharmaciesView.order_session_key, None)
        request.session.pop(ChoosePharmaciesView.selected_pharmacies_session_key, None)
        next_url = request.POST.get('next', '')
        if not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
        ):
            next_url = reverse('home')
        return redirect(next_url)


class ChoosePharmaciesView(RoleRequiredMixin, TemplateView):
    order_session_key = 'new_order'
    selected_pharmacies_session_key = 'chosen_pharmacies'
    template_name = 'orders/choose_pharmacies.html'
    partial_template_name = 'orders/_pharmacy_results.html'

    def allows(self, user):
        return user.is_customer

    def get_template_names(self):
        if self.request.htmx:
            return [self.partial_template_name]
        return [self.template_name]

    def get(self, request, *args, **kwargs):
        if request.session.get(self.order_session_key) is None:
            if request.htmx:
                return HttpResponse(headers={'HX-Redirect': reverse('orders:new')})
            return redirect('orders:new')
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):  # noqa: ARG002

        order = request.session.get(self.order_session_key)
        if order is None:
            return redirect('orders:new')

        selected_pharmacies_ids = [
            int(pharmacy_id) for pharmacy_id in request.POST.getlist('pharmacy')
        ]

        if not selected_pharmacies_ids:
            messages.error(request, 'Elegí al menos una farmacia.')
            return self.render_to_response(self.get_context_data())

        request.session[self.selected_pharmacies_session_key] = selected_pharmacies_ids

        messages.info(
            request,
            'Guardamos tu elección. El mail a las farmacias todavía no se envía.',
        )

        return redirect(request.get_full_path())

    def get_search_params(self, query):
        kinds = query.getlist('kinds')
        default_search_radius = SearchRadius.KM5.value

        if 'radius' not in query:
            customer_profile = get_account_client_profile(self.request.user.id)
            return {
                'radius_km': customer_profile.search_radius or default_search_radius,
                'include_pharmacies': True,
                'include_labs': True,
                'open_now': False,
                'home_delivery': False,
                'preparation': False,
            }

        return {
            'radius_km': int(query.get('radius', default_search_radius)),
            'include_pharmacies': 'pharmacy' in kinds,
            'include_labs': 'lab' in kinds,
            'open_now': 'open' in query,
            'home_delivery': 'delivery' in query,
            'preparation': 'preparation' in query,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.request.session.get(self.order_session_key)
        options = self.get_search_params(self.request.GET)

        pharmacies = find_nearby_pharmacies(
            origin=Coordinates.create(order['latitude'], order['longitude']),
            radius_km=SearchRadius(options['radius_km']),
            include_pharmacies=options['include_pharmacies'],
            include_labs=options['include_labs'],
            open_now=options['open_now'],
            home_delivery=options['home_delivery'],
            timezone=self.request.user.timezone,
            preparation_tag=(
                PreparationTag(order['preparation_tag'])
                if options['preparation']
                else None
            ),
        )

        chosen = set(self.request.session.get(self.selected_pharmacies_session_key, []))

        radius_options = [
            {'value': radius.value, 'label': f'Hasta {radius.value} km'}
            for radius in SearchRadius
        ]

        context.update(
            order=order,
            options=options,
            radius_options=radius_options,
            pharmacies=pharmacies,
            chosen=chosen,
            markers=[
                {
                    'id': pharmacy.id,
                    'name': pharmacy.name,
                    'latitude': pharmacy.latitude,
                    'longitude': pharmacy.longitude,
                }
                for pharmacy in pharmacies
            ],
        )

        return context
