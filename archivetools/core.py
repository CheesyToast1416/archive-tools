# Backwards-compatibility shim.
# All logic has moved to archivetools.formats, archivetools.operations, and archivetools.encoding.
# This module will be removed in a future release — update imports to the new locations.
from archivetools.formats import detect_handler
from archivetools.operations import create_archive, extract_cjk, list_cjk

__all__ = ["extract_cjk", "list_cjk", "detect_handler", "create_archive"]
