from dataclasses import asdict as dataclass_asdict
from dataclasses import is_dataclass
from datetime import time
from decimal import Decimal
from enum import Enum

from dacite import Config, DaciteError
from dacite import from_dict as dacite_from_dict

dacite_config = Config(
    type_hooks={time: time.fromisoformat, Decimal: Decimal},
    cast=[tuple, Enum],
)


def asdict(value):  # noqa: PLR0911
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, time):
        return value.strftime('%H:%M')
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, dict):
        return {key: asdict(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [asdict(item) for item in value]
    if is_dataclass(value):
        return asdict(dataclass_asdict(value))
    return value


def from_dict(data_class, raw):
    if not raw:
        return None
    try:
        return dacite_from_dict(data_class=data_class, data=raw, config=dacite_config)
    except DaciteError:
        return None
