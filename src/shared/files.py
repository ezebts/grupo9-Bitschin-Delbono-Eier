from django.core.files.base import File

KiB = 1024


def file_size_label(uploaded: File | None) -> str:
    """Returns a file size such as '980 KB' or '1,5 MB'."""

    if not uploaded:
        return ''

    try:
        size = uploaded.size
    except OSError:
        return ''

    if size < KiB:
        return f'{size} B'

    if size < KiB * KiB:
        return f'{round(size / KiB)} KB'

    mb = size / (KiB * KiB)

    return f'{mb:.1f} MB'.replace('.', ',')
