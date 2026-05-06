from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Optional


def create_archive(
        output_path: str | os.PathLike,
        files: Sequence[str | os.PathLike],
        *,
        format: str = "zip",
        password: Optional[str] = None,
        compression_level: int = 6,
        filename_encoding: Optional[str] = None,
) -> bool:
    """
    Create an archive from *files* at *output_path*.

    Supported formats (planned): "zip", "zip-aes", "7z", "tar",
    "tar.gz", "tar.bz2", "tar.xz".

    .. note::
        Archive creation is not yet implemented.
        This function establishes the API contract for the upcoming release.
    """
    raise NotImplementedError(
        "Archive creation is planned for the next release.\n"
        "Supported formats will be: ZIP, ZIP-AES, 7z, TAR family."
    )
