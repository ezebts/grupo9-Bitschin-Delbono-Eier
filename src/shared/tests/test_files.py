from django.core.files.base import ContentFile

from shared.files import file_size_label


def test_file_size_label_formats_bytes_kilobytes_and_megabytes():
    assert file_size_label(None) == ''
    assert file_size_label(ContentFile(b'x' * 980)) == '980 B'
    assert file_size_label(ContentFile(b'x' * 1024)) == '1 KB'
    assert file_size_label(ContentFile(b'x' * (1024 * 1024))) == '1,0 MB'
