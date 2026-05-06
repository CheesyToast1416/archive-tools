# Backwards-compatibility shim — will be removed in a future release.
# Import from the canonical locations instead:
#   from archivetools.operations import extract_archive, list_archive
#   from archivetools.formats import detect_handler
from archivetools.formats import detect_handler
from archivetools.operations import (
    create_archive,
    extract_archive,
    list_archive,
)

__all__ = [
    "extract_archive",
    "list_archive",
    "detect_handler",
    "create_archive",
]
