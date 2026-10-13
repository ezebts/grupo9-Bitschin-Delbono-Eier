from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

from shared.exceptions import Error


@dataclass(frozen=True)
class InvalidInvitationLinkError(Error):
    message = _('El enlace de invitación no es válido.')


@dataclass(frozen=True)
class InvalidCuitError(Error):
    message = _('El CUIT no es válido.')


@dataclass(frozen=True)
class InvalidSearchRadiusError(Error):
    message = _('Ingresá una distancia entre 1 y 300 km.')


@dataclass(frozen=True)
class InvalidDeliveryTermsError(Error):
    message = _('Elegí retiro, envío, o ambos.')


@dataclass(frozen=True)
class DeliveryCostWithoutHomeDeliveryError(Error):
    message = _(
        'El costo de envío solo se puede cargar si marcás envío a domicilio.',
    )


@dataclass(frozen=True)
class PharmacyCantBecomeVisible(Error):  # noqa: N818
    message = _(
        'Para aparecer en la búsqueda cargá el nombre comercial, '
        'el email para solicitudes y la ubicación.',
    )


@dataclass(frozen=True)
class PharmacyCantClearSearchData(Error):  # noqa: N818
    message = _(
        'Mientras estés visible no podés quitar el nombre comercial, '
        'el email para solicitudes ni la ubicación.',
    )
