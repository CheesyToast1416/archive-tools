from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from archivetools.operations.create import create_archive
from archivetools.operations.extract import extract_archive

log = logging.getLogger(__name__)


def convert_archive(
    input_path: str | os.PathLike,
    output_path: str | os.PathLike,
    output_format: str = "zip",
    *,
    password: str | None = None,
    output_password: str | None = None,
    filename_encoding: str | None = None,
    password_encoding: str | None = None,
) -> bool:
    """
    Re-package *input_path* into *output_path* using *output_format*.

    Extracts the source archive to a temporary directory, then creates a new
    archive in the target format.  Useful for converting RAR → ZIP, 7z → ZIP,
    or any format where re-encoding is needed.

    Parameters
    ----------
    input_path:
        Source archive (any supported format).
    output_path:
        Destination archive path.
    output_format:
        Target format: ``"zip"``, ``"zip-aes"``, ``"7z"``,
        ``"tar"``, ``"tar.gz"``, ``"tar.bz2"``, ``"tar.xz"``.
    password:
        Password for the *source* archive (if encrypted).
    output_password:
        Password to apply to the *output* archive (if the format supports it).
    filename_encoding / password_encoding:
        Encoding hints for the *source* archive.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    log.info(
        "Converting %s → %s (%s)", input_path.name, output_path.name, output_format
    )

    with tempfile.TemporaryDirectory(prefix="archivetools_convert_") as tmpdir:
        tmp = Path(tmpdir)

        # ── Extract source ────────────────────────────────────────────────────
        ok, enc = extract_archive(
            input_path,
            password or "",
            tmp,
            filename_encoding=filename_encoding,
            password_encoding=password_encoding,
            verbose=True,
        )
        if not ok:
            log.error("Conversion failed: could not extract source archive.")
            return False

        log.info(
            "Extraction complete (encoding: %s).  Creating %s…",
            enc or "auto",
            output_format.upper(),
        )

        # ── Re-package ────────────────────────────────────────────────────────
        extracted = sorted(tmp.iterdir())
        if not extracted:
            log.error("Conversion failed: source archive appears to be empty.")
            return False

        return create_archive(
            output_path,
            extracted,
            format=output_format,
            password=output_password,
        )
