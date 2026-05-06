from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from archivetools.encoding.candidates import password_candidates

log = logging.getLogger(__name__)


@dataclass
class ArchiveInfo:
    """Metadata about an archive, populated by ArchiveHandler.get_info()."""
    format_name: str
    file_count: int
    compressed_size: int    # bytes; -1 if unknown
    uncompressed_size: int  # bytes; -1 if unknown
    is_encrypted: bool
    comment: str = ""
    archive_path: Optional[Path] = field(default=None, repr=False)


class ArchiveHandler(ABC):
    """Common interface for all archive format handlers."""

    FORMAT_NAME: str = "archive"
    CAN_CREATE: bool = False         # handler supports archive creation
    CAN_ENCRYPT_CREATE: bool = False # handler supports encrypted creation

    # ── Password candidate resolution ────────────────────────────────────────

    @staticmethod
    def _resolve_candidates(
            password: str, password_encoding: Optional[str],
    ) -> list[tuple[bytes, str]]:
        """Return password byte candidates, optionally pinned to one encoding."""
        if password_encoding:
            try:
                return [(password.encode(password_encoding), password_encoding)]
            except (UnicodeEncodeError, LookupError):
                pass  # bad hint — fall back to auto-detect
        return password_candidates(password)

    # ── Extract ───────────────────────────────────────────────────────────────

    def extract(
            self,
            archive_path: Path,
            password: str,
            output_dir: Path,
            *,
            filename_encoding: Optional[str] = None,
            password_encoding: Optional[str] = None,
            verbose: bool = True,
            progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Try every CJK encoding for *password* and extract *archive_path*
        into *output_dir* with the first byte sequence that works.
        """
        candidates = self._resolve_candidates(password, password_encoding)
        if not candidates:
            log.error("Could not encode password with any known CJK encoding.")
            return False, None

        if verbose:
            log.info("Format   : %s", self.FORMAT_NAME)
            log.info("Archive  : %s", archive_path)
            log.info("Output   : %s", output_dir)
            if filename_encoding:
                log.info("Filename encoding: %s", filename_encoding)
            log.info(
                "Trying %d pwd encoding(s): %s",
                len(candidates),
                ", ".join(enc for _, enc in candidates),
            )

        for pwd_bytes, enc in candidates:
            if verbose:
                log.info("  → trying %-12s  bytes: %s", enc, pwd_bytes.hex(" "))
            try:
                if self._try_extract(archive_path, pwd_bytes, output_dir, filename_encoding,
                                     progress=progress):
                    if verbose:
                        log.info("✓ Success with encoding: %s", enc)
                    return True, enc
            except Exception as exc:  # noqa: BLE001
                log.error("Unexpected error with encoding %s: %s", enc, exc)
                return False, None

        log.error("✗ All encodings failed.  Check the password and try again.")
        return False, None

    # ── List contents ─────────────────────────────────────────────────────────

    def list_contents(
            self,
            archive_path: Path,
            password: str,
            filename_encoding: Optional[str] = None,
            password_encoding: Optional[str] = None,
    ) -> tuple[bool, Optional[str], list[str]]:
        """Return ``(success, encoding_used, file_names)`` without extracting."""
        for pwd_bytes, enc in self._resolve_candidates(password, password_encoding):
            try:
                names = self._list_names(archive_path, pwd_bytes, filename_encoding)
                if names is not None:
                    return True, enc, names
            except Exception:  # noqa: BLE001
                continue
        return False, None, []

    # ── Archive info (optional override) ─────────────────────────────────────

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        """Return basic archive metadata. Override in subclasses for richer data."""
        return ArchiveInfo(
            format_name=self.FORMAT_NAME,
            file_count=-1,
            compressed_size=-1,
            uncompressed_size=-1,
            is_encrypted=False,
            archive_path=archive_path,
        )

    # ── Create ────────────────────────────────────────────────────────────────

    def create(
            self,
            output_path: Path,
            files: list[Path],
            *,
            password: Optional[str] = None,
            compression_level: int = 6,
            filename_encoding: Optional[str] = None,
    ) -> bool:
        raise NotImplementedError(
            f"{self.FORMAT_NAME} handler does not support archive creation."
        )

    # ── Abstract primitives ───────────────────────────────────────────────────

    @abstractmethod
    def _try_extract(
            self,
            archive_path: Path,
            pwd_bytes: bytes,
            output_dir: Path,
            filename_encoding: Optional[str],
            progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> bool:
        pass

    @abstractmethod
    def _list_names(
            self,
            archive_path: Path,
            pwd_bytes: bytes,
            filename_encoding: Optional[str],
    ) -> Optional[list[str]]:
        pass
