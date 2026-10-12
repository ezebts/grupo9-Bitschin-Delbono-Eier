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
class QuoteDeliveryNotRequestedError(Error):
    message = 'Elegí una modalidad de entrega solicitada por el cliente.'


@dataclass(frozen=True)
class InvalidQuoteAmountError(Error):
    message = 'Los importes del presupuesto no son válidos.'


@dataclass(frozen=True)
class PickupDeliveryCostError(Error):
    message = 'El retiro en farmacia no puede tener costo de envío.'


@dataclass(frozen=True)
class MissingPreparationTimeError(Error):
    message = 'Indicá el plazo de preparación.'


@dataclass(frozen=True)
class ExpiredQuoteDateError(Error):
    message = 'La fecha de vencimiento no puede estar en el pasado.'
