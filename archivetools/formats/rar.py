from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from archivetools.formats.base import ArchiveHandler, ArchiveInfo

log = logging.getLogger(__name__)


class RarHandler(ArchiveHandler):
    FORMAT_NAME = "RAR"
    CAN_CREATE = False        # rarfile is read-only; RAR creation requires rar CLI
    CAN_ENCRYPT_CREATE = False

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
            self,
            archive_path: Path,
            pwd_bytes: bytes,
            output_dir: Path,
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
            self,
            archive_path: Path,
            pwd_bytes: bytes,
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

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        rf = self._import()
        try:
            with rf.RarFile(str(archive_path)) as rar:
                infos = rar.infolist()
                is_enc = any(getattr(i, "needs_password", lambda: False)() for i in infos)
                compressed = sum(
                    getattr(i, "compress_size", 0) or 0 for i in infos
                )
                uncompressed = sum(
                    getattr(i, "file_size", 0) or 0 for i in infos
                )
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
