from __future__ import annotations

import logging
import re
from pathlib import Path

from archivetools._multivolume import (
    _7z_first_part,
    _find_numbered_parts,
    _find_zip_split_parts,
    _rar_first_part,
)
from archivetools.formats.base import ArchiveHandler, ArchiveInfo
from archivetools.formats.rar import RarHandler
from archivetools.formats.sevenzip import SevenZipHandler
from archivetools.formats.tar import TarHandler
from archivetools.formats.zip import SplitZipHandler, ZipHandler, ZipHandlerAES, _sniff_zip_aes

log = logging.getLogger(__name__)

__all__ = [
    "ArchiveHandler",
    "ArchiveInfo",
    "ZipHandler",
    "ZipHandlerAES",
    "SplitZipHandler",
    "RarHandler",
    "SevenZipHandler",
    "TarHandler",
    "detect_handler",
]

# ── Format registry ───────────────────────────────────────────────────────────
# Maps lowercase extension → handler class.
# Used for capability queries and future plugin support.
FORMAT_REGISTRY: dict[str, type[ArchiveHandler]] = {
    ".zip": ZipHandler,
    ".rar": RarHandler,
    ".7z":  SevenZipHandler,
    ".tar": TarHandler,
}


def detect_handler(archive_path: Path) -> tuple[ArchiveHandler, Path]:
    """
    Return ``(handler, canonical_path)`` for *archive_path*.

    For multi-volume RAR/7z the canonical path is the first part.
    For split ZIPs the canonical path equals *archive_path* — assembly
    is handled internally by SplitZipHandler.
    """
    name = archive_path.name.lower()

    if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar")):
        return TarHandler(), archive_path

    # ── multi-volume / split detection ───────────────────────────────────────

    split_parts = _find_zip_split_parts(archive_path)
    if split_parts:
        log.info("Split ZIP detected (%d parts)", len(split_parts))
        return SplitZipHandler(split_parts), archive_path

    numbered = _find_numbered_parts(archive_path)
    if numbered:
        base_ext = Path(re.sub(r"\.\d+$", "", numbered[0].name)).suffix.lower()
        log.info(
            "Numbered split archive detected (%d parts, base extension: %s)",
            len(numbered), base_ext,
        )
        if base_ext == ".zip":
            return SplitZipHandler(numbered), archive_path
        if base_ext == ".7z":
            return SevenZipHandler(), _7z_first_part(archive_path)
        if base_ext == ".rar":
            return RarHandler(), _rar_first_part(archive_path)
        log.warning("Unknown split type '%s'; attempting ZIP assembly.", base_ext)
        return SplitZipHandler(numbered), archive_path

    if re.search(r"\.r\d+$", archive_path.name, re.IGNORECASE):
        return RarHandler(), _rar_first_part(archive_path)

    m = re.match(r"^.+\.part(\d+)\.rar$", archive_path.name, re.IGNORECASE)
    if m and int(m.group(1)) > 1:
        return RarHandler(), _rar_first_part(archive_path)

    # ── single-file detection ─────────────────────────────────────────────────
    suffix = archive_path.suffix.lower()
    if suffix == ".zip":
        if _sniff_zip_aes(archive_path):
            log.info("Detected WinZip AES-256 encryption — using pyzipper backend.")
            return ZipHandlerAES(), archive_path
        return ZipHandler(), archive_path
    if suffix == ".rar":
        return RarHandler(), archive_path
    if suffix == ".7z":
        return SevenZipHandler(), archive_path

    raise ValueError(f"Unsupported archive format: '{suffix}'")
