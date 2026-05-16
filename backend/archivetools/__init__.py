from archivetools.formats import detect_handler
from archivetools.formats.base import ArchiveInfo
from archivetools.operations import (
    convert_archive,
    create_archive,
    detect_archive_encoding,
    extract_archive,
    get_archive_info,
    list_archive,
    test_archive,
    update_archive,
)

__version__ = "0.2.0"
__all__ = [
    "extract_archive",
    "list_archive",
    "get_archive_info",
    "create_archive",
    "convert_archive",
    "test_archive",
    "update_archive",
    "detect_archive_encoding",
    "ArchiveInfo",
    "detect_handler",
    "__version__",
]
