from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archivetools.formats.base import ArchiveHandler

log = logging.getLogger(__name__)

_FORMAT_EXTENSIONS = {
    "zip": ".zip",
    "zip-aes": ".zip",
    "7z": ".7z",
    "tar": ".tar",
    "tar.gz": ".tar.gz",
    "tar.bz2": ".tar.bz2",
    "tar.xz": ".tar.xz",
}


def create_archive(
    output_path: str | os.PathLike,
    files: Sequence[str | os.PathLike],
    *,
    format: str = "zip",
    password: str | None = None,
    compression_level: int = 6,
    filename_encoding: str | None = None,
) -> bool:
    """
    Create an archive at *output_path* containing *files*.

    Parameters
    ----------
    output_path:
        Destination file path.  Extension should match the chosen format.
    files:
        Files and/or directories to include.  Directories are added recursively.
    format:
        One of: ``"zip"``, ``"zip-aes"``, ``"7z"``,
        ``"tar"``, ``"tar.gz"``, ``"tar.bz2"``, ``"tar.xz"``.
    password:
        Optional password.  Only meaningful for ``"zip-aes"`` and ``"7z"``.
    compression_level:
        0–9 (0 = store, 9 = maximum).  Ignored by formats that do not use it.
    filename_encoding:
        Reserved for future use; currently unused.
    """
    fmt = format.lower()
    if fmt not in _FORMAT_EXTENSIONS:
        raise ValueError(
            f"Unsupported format {format!r}. "
            f"Choose from: {', '.join(_FORMAT_EXTENSIONS)}"
        )

    output_path = Path(output_path)
    file_paths = [Path(f) for f in files]

    log.info("Creating %s archive: %s", fmt.upper(), output_path)
    log.info("Items: %d", len(file_paths))

    handler = _get_handler(fmt)
    return handler.create(
        output_path,
        file_paths,
        password=password,
        compression_level=compression_level,
        filename_encoding=filename_encoding,
    )


def _get_handler(fmt: str) -> ArchiveHandler:
    if fmt == "zip":
        from archivetools.formats.zip import ZipHandler

        return ZipHandler()
    if fmt == "zip-aes":
        from archivetools.formats.zip import ZipHandlerAES

        return ZipHandlerAES()
    if fmt == "7z":
        from archivetools.formats.sevenzip import SevenZipHandler

        return SevenZipHandler()
    # tar family
    from archivetools.formats.tar import TarHandler

    return TarHandler()
