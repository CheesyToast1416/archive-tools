from __future__ import annotations

import logging
import os
from pathlib import Path

from archivetools.formats import detect_handler

log = logging.getLogger(__name__)


def test_archive(
    archive_path: str | os.PathLike,
    password: str = "",
    *,
    filename_encoding: str | None = None,
    password_encoding: str | None = None,
) -> tuple[bool, list[str]]:
    """
    Verify archive integrity without extracting to disk.

    Returns ``(all_ok, failed_entry_names)``.
    ``failed_entry_names`` is an empty list when all entries pass.
    """
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    handler, canonical = detect_handler(archive_path)
    log.info("Testing %s: %s", handler.FORMAT_NAME, archive_path)

    ok, failed = handler.test(
        canonical,
        password,
        filename_encoding=filename_encoding,
        password_encoding=password_encoding,
    )

    if ok:
        log.info("✓ All entries passed integrity check.")
    else:
        log.warning("✗ %d entries failed: %s", len(failed), failed)

    return ok, failed
