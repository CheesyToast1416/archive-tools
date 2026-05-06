from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from archivetools.formats.base import ArchiveHandler, ArchiveInfo

log = logging.getLogger(__name__)


class ZipHandler(ArchiveHandler):
    FORMAT_NAME = "ZIP"
    CAN_CREATE = True
    CAN_ENCRYPT_CREATE = False  # stdlib zipfile cannot encrypt; use ZipHandlerAES

    def _fix_zipinfo_filename(
            self, info: zipfile.ZipInfo, filename_encoding: Optional[str],
    ) -> None:
        # Python's zipfile decodes non-UTF8 filenames as CP437.
        # Encode back to CP437 to get raw bytes, then decode with target codec.
        if filename_encoding and not (info.flag_bits & 0x800):
            try:
                raw_bytes = info.filename.encode("cp437")
                info.filename = raw_bytes.decode(filename_encoding)
            except UnicodeError:
                pass

    def _try_extract(
            self,
            archive_path: Path,
            pwd_bytes: bytes,
            output_dir: Path,
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
            self,
            archive_path: Path,
            pwd_bytes: bytes,
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

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        try:
            with zipfile.ZipFile(archive_path) as zf:
                infos = zf.infolist()
                is_enc = any(i.flag_bits & 0x1 for i in infos)
                compressed = sum(i.compress_size for i in infos)
                uncompressed = sum(i.file_size for i in infos)
                return ArchiveInfo(
                    format_name=self.FORMAT_NAME,
                    file_count=len(infos),
                    compressed_size=compressed,
                    uncompressed_size=uncompressed,
                    is_encrypted=is_enc,
                    comment=zf.comment.decode("utf-8", errors="replace") if zf.comment else "",
                    archive_path=archive_path,
                )
        except Exception:  # noqa: BLE001
            return super().get_info(archive_path)


class ZipHandlerAES(ZipHandler):
    FORMAT_NAME = "ZIP (AES-256)"
    CAN_CREATE = True
    CAN_ENCRYPT_CREATE = True

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
            self,
            archive_path: Path,
            pwd_bytes: bytes,
            output_dir: Path,
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
            self,
            archive_path: Path,
            pwd_bytes: bytes,
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


def _sniff_zip_aes(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as zf:
            return any(info.compress_type == 99 for info in zf.infolist())
    except Exception:
        return False


class SplitZipHandler(ZipHandler):
    """
    Handles ZIP archives split across numbered parts:
      • file.zip.001 / file.zip.002 / …  (WinRAR / 7-Zip generic split)
      • file.z01 / file.z02 / … / file.zip  (standard PKZip split)
    """

    FORMAT_NAME = "ZIP (split)"
    CAN_CREATE = False

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
