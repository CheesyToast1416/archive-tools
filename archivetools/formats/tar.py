from __future__ import annotations

import logging
import tarfile
from pathlib import Path
from typing import Optional

from archivetools.formats.base import ArchiveHandler, ArchiveInfo

log = logging.getLogger(__name__)


class TarHandler(ArchiveHandler):
    FORMAT_NAME = "TAR"
    CAN_CREATE = True
    CAN_ENCRYPT_CREATE = False  # TAR has no native encryption

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
        if password:
            raise TypeError(
                "TAR archives do not support encryption. "
                "Extract the outer ZIP/RAR/7z first, then open the TAR."
            )
        if verbose:
            log.info("Format   : %s", self.FORMAT_NAME)
            log.info("Archive  : %s", archive_path)
            log.info("Output   : %s", output_dir)
        try:
            with tarfile.open(archive_path) as tf:
                tf.extractall(path=output_dir)
            if verbose:
                log.info("✓ TAR extracted successfully.")
            return True, None
        except Exception as exc:  # noqa: BLE001
            log.error("TAR extraction failed: %s", exc)
            return False, None

    def list_contents(
            self,
            archive_path: Path,
            password: str,
            filename_encoding: Optional[str] = None,
            password_encoding: Optional[str] = None,
    ) -> tuple[bool, Optional[str], list[str]]:
        if password:
            raise TypeError("TAR archives do not support encryption.")
        try:
            with tarfile.open(archive_path) as tf:
                return True, None, tf.getnames()
        except Exception:  # noqa: BLE001
            return False, None, []

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        try:
            with tarfile.open(archive_path) as tf:
                members = tf.getmembers()
                uncompressed = sum(m.size for m in members)
                return ArchiveInfo(
                    format_name=self.FORMAT_NAME,
                    file_count=len(members),
                    compressed_size=archive_path.stat().st_size,
                    uncompressed_size=uncompressed,
                    is_encrypted=False,
                    archive_path=archive_path,
                )
        except Exception:  # noqa: BLE001
            return super().get_info(archive_path)

    def _try_extract(self, *_):
        raise NotImplementedError("TarHandler uses extract() directly.")

    def _list_names(self, *_):
        raise NotImplementedError("TarHandler uses list_contents() directly.")
