"""
archivetools.core
─────────────────
Extract password-protected archives created on Chinese Windows systems
where the password was encoded with a legacy CJK codepage instead of UTF-8.

Supported formats
-----------------
  .rar                      – via rarfile   (needs unrar / WinRAR on PATH)
  .zip                      – via zipfile   (stdlib) or pyzipper (AES-256)
  .7z                       – via py7zr
  .tar.gz / .tgz / .tar.*   – TAR has no password support; raises TypeError

Multi-volume archives
---------------------
  file.zip.001 / .zip.002 / …   – generic numbered split (WinRAR / 7-Zip)
  file.z01 / .z02 / … / .zip    – standard PKZip split format
  file.7z.001 / .7z.002 / …     – split 7z (py7zr handles natively)
  file.part1.rar / .part2.rar   – split RAR new-style (rarfile handles natively)
  file.rar / .r00 / .r01 / …    – split RAR old-style (rarfile handles natively)

Public API
----------
  extract_cjk(archive_path, password, output_dir=None, *, filename_encoding, verbose)
  list_cjk(archive_path, password, filename_encoding=None)
  detect_handler(archive_path) → (ArchiveHandler, canonical_path)
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import zipfile
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from archivetools._multivolume import (
    _7z_first_part,
    _find_numbered_parts,
    _find_zip_split_parts,
    _rar_first_part,
)

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CJK encoding helpers
# ─────────────────────────────────────────────────────────────────────────────

# Priority order: most-common Chinese Windows encodings first, UTF-8 last.
CJK_ENCODINGS: list[str] = [
    "gbk",       # CP936 – dominant on Mainland Chinese Windows
    "gb2312",    # strict GBK subset; usually an alias of GBK
    "gb18030",   # superset of GBK used on newer Mainland systems
    "big5",      # Traditional Chinese – Taiwan / Hong Kong
    "big5hkscs", # Hong Kong variant of BIG5
    "utf-8",     # Modern WinRAR ≥ 5.x / 7-Zip on any locale
]


def password_candidates(password: str) -> list[tuple[bytes, str]]:
    """
    Return a deduplicated list of ``(raw_bytes, encoding_name)`` pairs by
    encoding *password* through every CJK legacy encoding.
    """
    seen: set[bytes] = set()
    result: list[tuple[bytes, str]] = []
    for enc in CJK_ENCODINGS:
        try:
            raw = password.encode(enc)
        except (UnicodeEncodeError, LookupError):
            continue
        if raw not in seen:
            seen.add(raw)
            result.append((raw, enc))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base handler
# ─────────────────────────────────────────────────────────────────────────────

class ArchiveHandler(ABC):
    """Common interface for all archive format handlers."""

    FORMAT_NAME: str = "archive"

    @staticmethod
    def _resolve_candidates(
            password: str, password_encoding: Optional[str],
    ) -> list[tuple[bytes, str]]:
        """Return password byte candidates, optionally pinned to one encoding."""
        if password_encoding:
            try:
                return [(password.encode(password_encoding), password_encoding)]
            except (UnicodeEncodeError, LookupError):
                pass  # fall back to auto-detect if the hint is unusable
        return password_candidates(password)

    def extract(
            self,
            archive_path: Path,
            password: str,
            output_dir: Path,
            *,
            filename_encoding: Optional[str] = None,
            password_encoding: Optional[str] = None,
            verbose: bool = True,
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
                log.info("Filename encoding mapping: %s", filename_encoding)
            log.info(
                "Trying %d pwd encoding(s): %s",
                len(candidates),
                ", ".join(enc for _, enc in candidates),
            )

        for pwd_bytes, enc in candidates:
            if verbose:
                log.info("  → trying %-12s  bytes: %s", enc, pwd_bytes.hex(" "))
            try:
                if self._try_extract(archive_path, pwd_bytes, output_dir, filename_encoding):
                    if verbose:
                        log.info("✓ Success with encoding: %s", enc)
                    return True, enc
            except Exception as exc:  # noqa: BLE001
                log.error("Unexpected error with encoding %s: %s", enc, exc)
                return False, None

        log.error("✗ All encodings failed.  Check the password and try again.")
        return False, None

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

    @abstractmethod
    def _try_extract(
            self, archive_path: Path, pwd_bytes: bytes, output_dir: Path,
            filename_encoding: Optional[str],
    ) -> bool:
        pass

    @abstractmethod
    def _list_names(
            self, archive_path: Path, pwd_bytes: bytes,
            filename_encoding: Optional[str],
    ) -> Optional[list[str]]:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# ZIP handler  (stdlib zipfile)
# ─────────────────────────────────────────────────────────────────────────────

class ZipHandler(ArchiveHandler):
    FORMAT_NAME = "ZIP"

    def _fix_zipinfo_filename(
            self, info: zipfile.ZipInfo, filename_encoding: Optional[str],
    ) -> None:
        # Python's zipfile blindly decodes non-UTF8 filenames as CP437.
        # Encode back to CP437 to get raw bytes, then decode with target codec.
        if filename_encoding and not (info.flag_bits & 0x800):
            try:
                raw_bytes = info.filename.encode("cp437")
                info.filename = raw_bytes.decode(filename_encoding)
            except UnicodeError:
                pass

    def _try_extract(
            self, archive_path: Path, pwd_bytes: bytes, output_dir: Path,
            filename_encoding: Optional[str],
    ) -> bool:
        try:
            with zipfile.ZipFile(archive_path) as zf:
                for info in zf.infolist():
                    self._fix_zipinfo_filename(info, filename_encoding)
                    zf.extract(info, path=output_dir, pwd=pwd_bytes)
            return True
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "bad password" in msg or "password" in msg:
                return False
            if "aes" in msg or "requires" in msg:
                raise RuntimeError(
                    "This ZIP uses WinZip AES-256 encryption. "
                    "Install 'pyzipper' to decrypt."
                ) from exc
            raise
        except zipfile.BadZipFile:
            return False

    def _list_names(
            self, archive_path: Path, pwd_bytes: bytes,
            filename_encoding: Optional[str],
    ) -> Optional[list[str]]:
        try:
            with zipfile.ZipFile(archive_path) as zf:
                for info in zf.infolist():
                    if info.flag_bits & 0x1:  # encrypted flag
                        zf.open(info, pwd=pwd_bytes).read(1)
                        break
                names = []
                for info in zf.infolist():
                    self._fix_zipinfo_filename(info, filename_encoding)
                    names.append(info.filename)
                return names
        except RuntimeError:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# ZIP-AES handler  (pyzipper)
# ─────────────────────────────────────────────────────────────────────────────

class ZipHandlerAES(ZipHandler):
    FORMAT_NAME = "ZIP (AES-256)"

    @staticmethod
    def _open(archive_path: Path):
        try:
            import pyzipper  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "pyzipper is required for AES-encrypted ZIP files.\n"
                "Run:  pip install pyzipper"
            )
        return pyzipper.AESZipFile(archive_path)

    def _try_extract(
            self, archive_path: Path, pwd_bytes: bytes, output_dir: Path,
            filename_encoding: Optional[str],
    ) -> bool:
        try:
            with self._open(archive_path) as zf:
                for info in zf.infolist():
                    self._fix_zipinfo_filename(info, filename_encoding)
                    zf.extract(info, path=output_dir, pwd=pwd_bytes)
            return True
        except RuntimeError as exc:
            if "password" in str(exc).lower():
                return False
            raise
        except Exception as exc:  # noqa: BLE001
            if "password" in str(exc).lower() or "bad" in str(exc).lower():
                return False
            raise

    def _list_names(
            self, archive_path: Path, pwd_bytes: bytes,
            filename_encoding: Optional[str],
    ) -> Optional[list[str]]:
        try:
            with self._open(archive_path) as zf:
                zf.setpassword(pwd_bytes)
                names = []
                for info in zf.infolist():
                    self._fix_zipinfo_filename(info, filename_encoding)
                    names.append(info.filename)
                return names
        except Exception:  # noqa: BLE001
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Split-ZIP handler  (concatenates numbered parts, then delegates)
# ─────────────────────────────────────────────────────────────────────────────

class SplitZipHandler(ZipHandler):
    """
    Handles ZIP archives split across numbered parts:
      • file.zip.001 / file.zip.002 / …  (WinRAR / 7-Zip generic split)
      • file.z01 / file.z02 / … / file.zip  (standard PKZip split)
    """

    FORMAT_NAME = "ZIP (split)"

    def __init__(self, parts: list[Path]) -> None:
        self._parts = parts

    @contextmanager
    def _assembled(self) -> Iterator[Path]:
        """Concatenate all parts into a single temp file and yield its Path."""
        fd, tmp_name = tempfile.mkstemp(suffix=".zip")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as tmp:
                for part in self._parts:
                    with part.open("rb") as src:
                        shutil.copyfileobj(src, tmp)
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)

    def _delegate(self, tmp_path: Path) -> ZipHandler:
        if _sniff_zip_aes(tmp_path):
            log.info("Detected WinZip AES-256 in split archive — using pyzipper.")
            return ZipHandlerAES()
        return ZipHandler()

    def extract(
        self,
        archive_path: Path,
        password: str,
        output_dir: Path,
        *,
        filename_encoding: Optional[str] = None,
        password_encoding: Optional[str] = None,
        verbose: bool = True,
    ) -> tuple[bool, Optional[str]]:
        if verbose:
            log.info("Split ZIP  : assembling %d parts into temp file…", len(self._parts))
            for p in self._parts:
                log.info("  part : %s", p.name)
        with self._assembled() as tmp_path:
            return self._delegate(tmp_path).extract(
                tmp_path, password, output_dir,
                filename_encoding=filename_encoding,
                password_encoding=password_encoding,
                verbose=verbose,
            )

    def list_contents(
        self,
        archive_path: Path,
        password: str,
        filename_encoding: Optional[str] = None,
        password_encoding: Optional[str] = None,
    ) -> tuple[bool, Optional[str], list[str]]:
        with self._assembled() as tmp_path:
            return self._delegate(tmp_path).list_contents(
                tmp_path, password, filename_encoding, password_encoding,
            )


# ─────────────────────────────────────────────────────────────────────────────
# RAR handler  (rarfile)
# ─────────────────────────────────────────────────────────────────────────────

class RarHandler(ArchiveHandler):
    FORMAT_NAME = "RAR"

    @staticmethod
    def _import():
        try:
            import rarfile  # type: ignore[import]
            return rarfile
        except ImportError:
            raise ImportError(
                "rarfile is required for RAR archives.\n"
                "Run:  pip install rarfile"
            )

    def _try_extract(
            self, archive_path: Path, pwd_bytes: bytes, output_dir: Path,
            filename_encoding: Optional[str],
    ) -> bool:
        rf = self._import()
        kwargs = {"charset": filename_encoding} if filename_encoding else {}
        try:
            with rf.RarFile(str(archive_path), **kwargs) as rar:
                rar.extractall(path=str(output_dir), pwd=pwd_bytes)
            return True
        except rf.BadRarPassword:
            return False
        except rf.RarCRCError:
            return False

    def _list_names(
            self, archive_path: Path, pwd_bytes: bytes,
            filename_encoding: Optional[str],
    ) -> Optional[list[str]]:
        rf = self._import()
        kwargs = {"charset": filename_encoding} if filename_encoding else {}
        try:
            with rf.RarFile(str(archive_path), **kwargs) as rar:
                rar.setpassword(pwd_bytes)
                for info in rar.infolist():
                    if info.needs_password():
                        rar.open(info, pwd=pwd_bytes).read(1)
                        break
                return rar.namelist()
        except (rf.BadRarPassword, rf.RarCRCError):
            return None


# ─────────────────────────────────────────────────────────────────────────────
# 7z handler  (py7zr)
# ─────────────────────────────────────────────────────────────────────────────

class SevenZipHandler(ArchiveHandler):
    FORMAT_NAME = "7z"

    @staticmethod
    def _import():
        try:
            import py7zr  # type: ignore[import]
            return py7zr
        except ImportError:
            raise ImportError("Run:  pip install py7zr")

    def _str_candidates(
            self, password: str, password_encoding: Optional[str] = None,
    ) -> list[tuple[str, str]]:
        seen: set[str] = set()
        result: list[tuple[str, str]] = []

        def _add(s: str, label: str) -> None:
            if s not in seen:
                seen.add(s)
                result.append((s, label))

        _add(password, "utf-8 (str)")
        for raw, enc in self._resolve_candidates(password, password_encoding):
            try:
                proxy = raw.decode("latin-1")
                _add(proxy, f"{enc}→latin-1 proxy")
            except Exception:  # noqa: BLE001
                pass
        return result

    def _try_extract(self, *args, **kwargs):
        raise NotImplementedError("Use extract() directly for 7z archives.")

    def _list_names(self, *args, **kwargs):
        raise NotImplementedError("Use list_contents() directly for 7z archives.")

    def extract(
            self, archive_path: Path, password: str, output_dir: Path,
            *, filename_encoding: Optional[str] = None,
            password_encoding: Optional[str] = None, verbose: bool = True,
    ) -> tuple[bool, Optional[str]]:
        # 7z stores filenames in UTF-16; filename_encoding is intentionally ignored.
        py7zr = self._import()
        str_candidates = self._str_candidates(password, password_encoding)

        if verbose:
            log.info("Format   : %s", self.FORMAT_NAME)
            log.info("Trying %d password variant(s)", len(str_candidates))

        for pwd_str, label in str_candidates:
            try:
                with py7zr.SevenZipFile(str(archive_path), mode="r", password=pwd_str) as sz:
                    sz.extractall(path=str(output_dir))
                return True, label
            except (py7zr.exceptions.PasswordRequired, py7zr.exceptions.Bad7zFile):
                continue
            except Exception:  # noqa: BLE001
                continue

        return False, None

    def list_contents(
            self, archive_path: Path, password: str,
            filename_encoding: Optional[str] = None,
            password_encoding: Optional[str] = None,
    ) -> tuple[bool, Optional[str], list[str]]:
        py7zr = self._import()
        for pwd_str, label in self._str_candidates(password, password_encoding):
            try:
                with py7zr.SevenZipFile(str(archive_path), mode="r", password=pwd_str) as sz:
                    return True, label, sz.getnames()
            except Exception:  # noqa: BLE001
                continue
        return False, None, []


# ─────────────────────────────────────────────────────────────────────────────
# TAR handler  (stdlib tarfile — informational only)
# ─────────────────────────────────────────────────────────────────────────────

class TarHandler(ArchiveHandler):
    FORMAT_NAME = "TAR"

    def extract(self, archive_path, password, output_dir, *, filename_encoding=None, verbose=True):
        raise TypeError("TAR archives do not support encryption. Extract the outer ZIP/RAR first.")

    def list_contents(self, archive_path, password, filename_encoding=None):
        self.extract(archive_path, password, Path("."))

    def _try_extract(self, *_):
        raise NotImplementedError

    def _list_names(self, *_):
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# Format detection
# ─────────────────────────────────────────────────────────────────────────────

def _sniff_zip_aes(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as zf:
            return any(info.compress_type == 99 for info in zf.infolist())
    except Exception:
        return False


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

    # Standard PKZip split: .z01 / .z02 / ... / .zip
    split_parts = _find_zip_split_parts(archive_path)
    if split_parts:
        log.info("Split ZIP detected (%d parts)", len(split_parts))
        return SplitZipHandler(split_parts), archive_path

    # Numbered split: file.ext.001 / file.ext.002 / ...
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

    # Old-style RAR volumes: .r00 / .r01 / ...
    if re.search(r"\.r\d+$", archive_path.name, re.IGNORECASE):
        return RarHandler(), _rar_first_part(archive_path)

    # New-style RAR not at part 1: .part02.rar / .part03.rar / ...
    m = re.match(r"^.+\.part(\d+)\.rar$", archive_path.name, re.IGNORECASE)
    if m and int(m.group(1)) > 1:
        return RarHandler(), _rar_first_part(archive_path)

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


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

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


def list_cjk(
        archive_path: str | os.PathLike,
        password: str,
        filename_encoding: Optional[str] = None,
        password_encoding: Optional[str] = None,
) -> tuple[bool, Optional[str], list[str]]:
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    handler, canonical = detect_handler(archive_path)
    return handler.list_contents(
        canonical, password, filename_encoding, password_encoding,
    )
