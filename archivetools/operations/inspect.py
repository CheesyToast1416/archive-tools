from __future__ import annotations

import os
from pathlib import Path

from archivetools.formats import detect_handler
from archivetools.formats.base import ArchiveInfo


def list_archive(
    archive_path: str | os.PathLike,
    password: str,
    filename_encoding: str | None = None,
    password_encoding: str | None = None,
) -> tuple[bool, str | None, list[str]]:
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    handler, canonical = detect_handler(archive_path)
    return handler.list_contents(
        canonical, password, filename_encoding, password_encoding
    )


def get_archive_info(
    archive_path: str | os.PathLike,
) -> ArchiveInfo:
    """Return archive metadata without requiring a password."""
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    handler, canonical = detect_handler(archive_path)
    return handler.get_info(canonical)


def detect_archive_encoding(
    archive_path: str | os.PathLike,
) -> tuple[str | None, float]:
    """
    Auto-detect the filename encoding used in a ZIP or RAR archive.

    Returns ``(encoding_name, confidence)`` where confidence is 0.0–1.0.
    Returns ``(None, 0.0)`` for non-ZIP/RAR archives, missing files, or when
    detection is inconclusive.

    This is the operations-layer facade over ``archivetools.encoding.detect``.
    GUI code must call this rather than importing from ``encoding`` directly.
    """
    path = Path(archive_path)
    name = path.name.lower()
    if name.endswith((".zip", ".z01")):
        from archivetools.encoding.detect import detect_zip_filename_encoding

        return detect_zip_filename_encoding(path)
    if name.endswith((".rar", ".r00", ".r01")):
        from archivetools.encoding.detect import detect_rar_filename_encoding

        return detect_rar_filename_encoding(path)
    return None, 0.0
