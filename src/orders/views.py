from http import HTTPStatus

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import FormView

from orders.forms import NewOrderForm
from shared.dataclasses import asdict
from shared.places import PlaceSearchUnavailableError, find_place, search_places
from shared.values import Coordinates, InvalidCoordinatesError
from shared.views import RoleRequiredMixin


class NewOrderView(RoleRequiredMixin, FormView):
    form_class = NewOrderForm
    template_name = 'orders/new_order.html'

    def allows(self, user):
        return user.is_customer

    def form_valid(self, form):
        if 'save_draft' in self.request.POST:
            messages.info(self.request, 'Todavía no se pueden guardar borradores.')
        else:
            messages.info(
                self.request,
                'Tu solicitud está completa. '
                'Elegir farmacias todavía no está disponible.',
            )
        return self.render_to_response(self.get_context_data(form=form))


class PlaceSearchView(LoginRequiredMixin, View):
    min_length = 3
    max_length = 200

    def get(self, request):
        try:
            places = self._places(request.GET)
        except InvalidCoordinatesError as error:
            return self._error(error, HTTPStatus.BAD_REQUEST)
        except PlaceSearchUnavailableError as error:
            return self._error(error, HTTPStatus.SERVICE_UNAVAILABLE)
        return JsonResponse({'places': [asdict(place) for place in places]})

    def _places(self, params):
        if 'latitude' in params:
            coordinates = Coordinates.create(
                params.get('latitude'),
                params.get('longitude'),
            )
            place = find_place(coordinates)
            return (place,) if place else ()
        text = params.get('q', '').strip()[: self.max_length]
        if len(text) < self.min_length:
            return ()
        return search_places(text)

    @staticmethod
    def _error(error, status):
        return JsonResponse({'error': str(error.message)}, status=status)
