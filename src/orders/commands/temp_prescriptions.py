import uuid
from pathlib import PurePosixPath

from django.core.files import File
from django.core.files.storage import default_storage

TEMP_PRESCRIPTIONS_PATH = PurePosixPath('orders/prescriptions/pending')


def _is_temp_path(path):

    if not path:
        return False

    pure = PurePosixPath(path)

    return (
        not pure.is_absolute()
        and '..' not in pure.parts
        and pure.is_relative_to(TEMP_PRESCRIPTIONS_PATH)
        and pure != TEMP_PRESCRIPTIONS_PATH
    )


def save_temp_prescription(prescription_file: File) -> str:
    filename = PurePosixPath(prescription_file.name).name
    return default_storage.save(
        f'{TEMP_PRESCRIPTIONS_PATH}/{uuid.uuid4().hex}/{filename}',
        prescription_file,
    )


def delete_temp_prescription(path: str):
    if _is_temp_path(path):
        default_storage.delete(path)


def open_temp_prescription(path: str) -> File | None:
    if not _is_temp_path(path) or not default_storage.exists(path):
        return None
    stored = default_storage.open(path)
    return File(stored, name=PurePosixPath(path).name)
