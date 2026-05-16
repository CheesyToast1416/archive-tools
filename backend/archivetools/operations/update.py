from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)


def update_archive(
    archive_path: str | Path,
    *,
    files_to_add: list[str | Path] | None = None,
    paths_to_remove: list[str] | None = None,
) -> bool:
    """
    Add or remove entries in an existing archive in-place.

    *files_to_add*     — local filesystem paths (files or dirs) to append.
    *paths_to_remove*  — archive entry names (e.g. "folder/file.txt") to delete.

    Supported formats: ZIP, 7z, TAR family.
    RAR archives are read-only and will raise ``NotImplementedError``.
    Returns True on success.
    """
    archive_path = Path(archive_path)
    add: list[Path] = [Path(f) for f in (files_to_add or [])]
    remove: set[str] = set(paths_to_remove or [])

    if not add and not remove:
        return True

    ext = archive_path.suffix.lower()
    name_lower = archive_path.name.lower()

    if name_lower.endswith((".rar", ".r00", ".r01")):
        raise NotImplementedError("RAR archives are read-only and cannot be modified.")

    if ext == ".zip" or name_lower.endswith((".z01",)):
        return _update_zip(archive_path, add, remove)

    if ext == ".7z":
        return _update_7z(archive_path, add, remove)

    if ext in (".tar", ".gz", ".bz2", ".xz", ".tgz") or ".tar." in name_lower:
        return _update_tar(archive_path, add, remove)

    raise ValueError(
        f"Unsupported archive format for in-place update: {archive_path.name}"
    )


# ── ZIP ───────────────────────────────────────────────────────────────────────


def _update_zip(archive_path: Path, add: list[Path], remove: set[str]) -> bool:
    if remove:
        # Rebuild: copy kept entries to a temp file, then append new files
        tmp_fd, tmp_path_str = tempfile.mkstemp(
            suffix=".tmp", dir=archive_path.parent, prefix=".atupdate_"
        )
        os.close(tmp_fd)
        tmp_path = Path(tmp_path_str)
        try:
            with zipfile.ZipFile(archive_path, "r") as src:
                with zipfile.ZipFile(
                    tmp_path, "w", compression=zipfile.ZIP_DEFLATED
                ) as dst:
                    for info in src.infolist():
                        if info.filename not in remove:
                            dst.writestr(info, src.read(info.filename))
            if add:
                with zipfile.ZipFile(tmp_path, "a") as zf:
                    for f in add:
                        _zip_add(zf, f)
            tmp_path.replace(archive_path)
            log.info("Updated ZIP: %s", archive_path.name)
            return True
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    else:
        # Append only — no rebuild needed
        with zipfile.ZipFile(archive_path, "a") as zf:
            for f in add:
                _zip_add(zf, f)
        log.info("Appended to ZIP: %s", archive_path.name)
        return True


def _zip_add(zf: zipfile.ZipFile, path: Path) -> None:
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                zf.write(child, child.relative_to(path.parent))
    elif path.is_file():
        zf.write(path, path.name)


# ── 7z ───────────────────────────────────────────────────────────────────────


def _update_7z(archive_path: Path, add: list[Path], remove: set[str]) -> bool:
    import py7zr  # type: ignore[import]

    tmpdir = tempfile.mkdtemp(prefix="atupdate_")
    tmp_archive = archive_path.with_suffix(".atupdate.7z")
    try:
        # Extract entries that should be kept
        with py7zr.SevenZipFile(archive_path, "r") as sz:
            all_names = sz.getnames()
            keep = [n for n in all_names if n not in remove]
            if keep:
                sz.extract(targets=keep, path=tmpdir)

        # Create new archive from tmpdir + new files
        with py7zr.SevenZipFile(tmp_archive, "w") as sz:
            for root, _dirs, files in os.walk(tmpdir):
                for fname in files:
                    full = os.path.join(root, fname)
                    arc_name = os.path.relpath(full, tmpdir)
                    sz.write(full, arc_name)
            for f in add:
                f = Path(f)
                if f.is_dir():
                    for child in sorted(f.rglob("*")):
                        if child.is_file():
                            sz.write(str(child), str(child.relative_to(f.parent)))
                elif f.is_file():
                    sz.write(str(f), f.name)

        tmp_archive.replace(archive_path)
        log.info("Updated 7z: %s", archive_path.name)
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        tmp_archive.unlink(missing_ok=True)


# ── TAR ───────────────────────────────────────────────────────────────────────


def _update_tar(archive_path: Path, add: list[Path], remove: set[str]) -> bool:
    import tarfile

    name_lower = archive_path.name.lower()
    if name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
        mode_r, mode_w = "r:gz", "w:gz"
    elif name_lower.endswith(".tar.bz2"):
        mode_r, mode_w = "r:bz2", "w:bz2"
    elif name_lower.endswith(".tar.xz"):
        mode_r, mode_w = "r:xz", "w:xz"
    else:
        mode_r, mode_w = "r:", "w:"

    tmp_fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp", dir=archive_path.parent, prefix=".atupdate_"
    )
    os.close(tmp_fd)
    tmp_path = Path(tmp_path_str)
    try:
        with tarfile.open(archive_path, mode_r) as src:  # type: ignore[call-overload]
            with tarfile.open(tmp_path, mode_w) as dst:  # type: ignore[call-overload]
                for member in src.getmembers():
                    if member.name not in remove:
                        fobj = src.extractfile(member)
                        dst.addfile(member, fobj)
        with tarfile.open(tmp_path, "a") as dst:
            for f in add:
                f = Path(f)
                dst.add(str(f), arcname=f.name, recursive=True)
        tmp_path.replace(archive_path)
        log.info("Updated TAR: %s", archive_path.name)
        return True
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
