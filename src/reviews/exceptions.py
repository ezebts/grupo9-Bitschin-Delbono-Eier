from dataclasses import dataclass

from shared.exceptions import Error


@dataclass(frozen=True)
class ReviewNotAllowedError(Error):
    message = 'Este pedido todavía no se puede reseñar.'


@dataclass(frozen=True)
class ReviewAlreadySentError(Error):
    message = 'Ya dejaste una reseña para este pedido.'
