from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from archivetools.formats.base import ArchiveHandler, ArchiveInfo

log = logging.getLogger(__name__)


class RarHandler(ArchiveHandler):
    FORMAT_NAME = "RAR"
    CAN_CREATE = False  # rarfile is read-only; RAR creation requires rar CLI
    CAN_ENCRYPT_CREATE = False

    @staticmethod
    def _import() -> Any:
        try:
            import rarfile  # type: ignore[import]

            return rarfile
        except ImportError:
            raise ImportError(
                "rarfile is required for RAR archives.\nRun:  pip install rarfile"
            )

    def _try_extract(
        self,
        archive_path: Path,
        pwd_bytes: bytes,
        output_dir: Path,
        filename_encoding: str | None,
        progress: Callable[[int, int, str], None] | None = None,
        bytes_progress: Callable[[int, int], None] | None = None,
    ) -> bool:
        rf = self._import()
        kwargs = {"charset": filename_encoding} if filename_encoding else {}
        try:
            with rf.RarFile(str(archive_path), **kwargs) as rar:
                infos = rar.infolist()
                total = len(infos)
                for i, info in enumerate(infos):
                    rar.extract(info, path=str(output_dir), pwd=pwd_bytes)
                    if progress:
                        progress(i + 1, total, info.filename)
            return True
        except rf.BadRarPassword:
            return False
        except rf.RarCRCError:
            return False

    def _list_names(
        self,
        archive_path: Path,
        pwd_bytes: bytes,
        filename_encoding: str | None,
    ) -> list[str] | None:
        rf = self._import()
        kwargs = {"charset": filename_encoding} if filename_encoding else {}
        try:
            with rf.RarFile(str(archive_path), **kwargs) as rar:
                rar.setpassword(pwd_bytes)
                for info in rar.infolist():
                    if info.needs_password():
                        rar.open(info, pwd=pwd_bytes).read(1)
                        break
                return list(rar.namelist())
        except (rf.BadRarPassword, rf.RarCRCError):
            return None

    def test(
        self,
        archive_path: Path,
        password: str,
        *,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
    ) -> tuple[bool, list[str]]:
        rf = self._import()
        candidates = self._resolve_candidates(password, password_encoding)
        for pwd_bytes, _enc in candidates:
            try:
                with rf.RarFile(str(archive_path)) as rar:
                    rar.setpassword(pwd_bytes)
                    bad = rar.testrar()  # returns None on success or raises
                return True, list(bad) if bad else []
            except rf.BadRarPassword:
                continue
            except rf.RarCRCError as exc:
                return False, [str(exc)]
            except Exception:  # noqa: BLE001
                continue
        return False, ["Wrong password or could not open archive"]

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        rf = self._import()
        try:
            with rf.RarFile(str(archive_path)) as rar:
                infos = rar.infolist()
                is_enc = any(
                    getattr(i, "needs_password", lambda: False)() for i in infos
                )
                compressed = sum(getattr(i, "compress_size", 0) or 0 for i in infos)
                uncompressed = sum(getattr(i, "file_size", 0) or 0 for i in infos)
                return ArchiveInfo(
                    format_name=self.FORMAT_NAME,
                    file_count=len(infos),
                    compressed_size=compressed,
                    uncompressed_size=uncompressed,
                    is_encrypted=is_enc,
                    archive_path=archive_path,
                )
        except Exception:  # noqa: BLE001
            return super().get_info(archive_path)
