from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

from shared.exceptions import Error


@dataclass(frozen=True)
class InvalidCuitError(Error):
    message = _('El CUIT no es válido.')


@dataclass(frozen=True)
class InvalidDeliveryTermsError(Error):
    message = _('Elegí retiro, envío, o ambos. El envío necesita radio y costo.')
