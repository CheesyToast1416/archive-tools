from __future__ import annotations

import re
from pathlib import Path


def _find_numbered_parts(path: Path) -> list[Path]:
    """
    Detect file.ext.001 / file.ext.002 / … splits.
    Returns sorted part list when ≥ 2 parts are found, else [].
    """
    m = re.match(r"^(.+)\.(\d+)$", path.name)
    if not m:
        return []
    base = m.group(1)
    parts = sorted(
        (
            p
            for p in path.parent.iterdir()
            if re.fullmatch(rf"{re.escape(base)}\.\d+", p.name)
        ),
        key=lambda p: int(p.suffix.lstrip(".")),
    )
    return parts if len(parts) > 1 else []


def _find_zip_split_parts(path: Path) -> list[Path]:
    """
    Detect standard PKZip split: file.z01 / file.z02 / … / file.zip.
    Works whether *path* is one of the .zNN parts or the final .zip.
    Returns the full sorted part list (including the .zip) when found, else [].
    """
    name = path.name
    parent = path.parent

    if re.search(r"\.z\d+$", name, re.IGNORECASE):
        base = re.sub(r"\.z\d+$", "", name, flags=re.IGNORECASE)
    elif path.suffix.lower() == ".zip":
        base = path.stem
        has_z_parts = any(
            re.fullmatch(rf"{re.escape(base)}\.z\d+", p.name, re.IGNORECASE)
            for p in parent.iterdir()
        )
        if not has_z_parts:
            return []
    else:
        return []

    z_parts = sorted(
        (
            p
            for p in parent.iterdir()
            if re.fullmatch(rf"{re.escape(base)}\.z\d+", p.name, re.IGNORECASE)
        ),
        key=lambda p: int(re.sub(r"\D", "", p.suffix)),
    )
    final = parent / f"{base}.zip"
    return (z_parts + [final]) if (z_parts and final.exists()) else z_parts


def _rar_first_part(path: Path) -> Path:
    """Return the first volume of a multi-part RAR set."""
    m = re.match(r"^(.+)\.part\d+\.rar$", path.name, re.IGNORECASE)
    if m:
        first = path.parent / f"{m.group(1)}.part1.rar"
        return first if first.exists() else path
    m = re.match(r"^(.+)\.r\d+$", path.name, re.IGNORECASE)
    if m:
        first = path.parent / f"{m.group(1)}.rar"
        return first if first.exists() else path
    return path


def _7z_first_part(path: Path) -> Path:
    """Return the first volume of a split 7z set (.7z.001)."""
    m = re.match(r"^(.+\.7z)\.\d+$", path.name, re.IGNORECASE)
    if m:
        first = path.parent / f"{m.group(1)}.001"
        return first if first.exists() else path
    return path
