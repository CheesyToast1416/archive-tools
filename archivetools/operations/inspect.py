from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from archivetools.formats import detect_handler
from archivetools.formats.base import ArchiveInfo


def list_cjk(
        archive_path: str | os.PathLike,
        password: str,
        filename_encoding: Optional[str] = None,
        password_encoding: Optional[str] = None,
) -> tuple[bool, Optional[str], list[str]]:
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    handler, canonical = detect_handler(archive_path)
    return handler.list_contents(canonical, password, filename_encoding, password_encoding)


def get_archive_info(
        archive_path: str | os.PathLike,
) -> ArchiveInfo:
    """Return archive metadata without requiring a password."""
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    handler, canonical = detect_handler(archive_path)
    return handler.get_info(canonical)
