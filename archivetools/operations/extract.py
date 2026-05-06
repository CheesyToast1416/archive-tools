from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from archivetools.formats import detect_handler


def _default_output_dir(archive_path: Path) -> Path:
    """Derive a clean output directory name from the archive path."""
    stem = archive_path.name
    stem = re.sub(r"\.\d+$", "", stem)  # strip trailing .001 / .002 etc.
    for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz"):
        if stem.lower().endswith(ext):
            return archive_path.parent / stem[: -len(ext)]
    p = Path(stem)
    if p.suffix.lower() in (".zip", ".rar", ".7z", ".z"):
        stem = p.stem
    return archive_path.parent / (stem or archive_path.stem)


def extract_cjk(
        archive_path: str | os.PathLike,
        password: str,
        output_dir: Optional[str | os.PathLike] = None,
        *,
        filename_encoding: Optional[str] = None,
        password_encoding: Optional[str] = None,
        verbose: bool = True,
) -> tuple[bool, Optional[str]]:
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    if output_dir is None:
        output_dir = _default_output_dir(archive_path)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    handler, canonical = detect_handler(archive_path)
    return handler.extract(
        canonical, password, output_dir,
        filename_encoding=filename_encoding,
        password_encoding=password_encoding,
        verbose=verbose,
    )
