from dataclasses import dataclass

from shared.exceptions import Error


@dataclass(frozen=True)
class QuoteCannotBeSubmittedError(Error):
    message = 'Esta solicitud ya no puede recibir un presupuesto.'


@dataclass(frozen=True)
class QuoteCannotBeEditedError(Error):
    message = 'Solo podés editar un presupuesto sin respuesta.'


@dataclass(frozen=True)
class QuoteCannotBeWithdrawnError(Error):
    message = 'Solo podés retirar un presupuesto sin respuesta.'


@dataclass(frozen=True)
class QuoteCannotBeAnsweredError(Error):
    message = 'Este presupuesto ya no se puede aceptar ni rechazar.'


@dataclass(frozen=True)
class ExpiredQuoteError(Error):
    message = 'Este presupuesto ya venció.'


@dataclass(frozen=True)
class OrderCannotAdvanceError(Error):
    message = 'Este pedido ya no se puede avanzar.'


@dataclass(frozen=True)
class InvalidEstimatedDateError(Error):
    message = 'Indicá una fecha estimada desde hoy en adelante.'


@dataclass(frozen=True)
class InvalidQuotePriceError(Error):
    message = 'Ingresá un monto mayor a cero.'


@dataclass(frozen=True)
class InvalidDeliveryCostError(Error):
    message = 'El envío a domicilio tiene que tener un costo mayor a cero.'


@dataclass(frozen=True)
class ExpiredQuoteDateError(Error):
    message = 'La fecha de vencimiento no puede estar en el pasado.'
