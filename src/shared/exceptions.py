from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Error(Exception):
    def __post_init__(self) -> None:
        Exception.__init__(self)

    def __str__(self) -> str:
        return repr(self)

    @property
    def code(self) -> str:
        return type(self).__name__

    @property
    def details(self) -> dict[str, Any]:
        return asdict(self)
