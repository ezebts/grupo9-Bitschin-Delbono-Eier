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
class InvalidQuotePriceError(Error):
    message = 'Ingresá un monto mayor a cero.'


@dataclass(frozen=True)
class InvalidDeliveryCostError(Error):
    message = 'El envío a domicilio tiene que tener un costo mayor a cero.'


@dataclass(frozen=True)
class ExpiredQuoteDateError(Error):
    message = 'La fecha de vencimiento no puede estar en el pasado.'
