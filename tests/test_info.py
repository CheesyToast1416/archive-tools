from __future__ import annotations

import tarfile
import zipfile

import pytest

from archivetools.operations import get_archive_info


class TestGetArchiveInfo:
    def test_zip_info(self, tmp_path):
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("hello.txt", "world")
            zf.writestr("data.csv", "a,b,c")
        info = get_archive_info(p)
        assert info.format_name == "ZIP"
        assert info.file_count == 2
        assert info.is_encrypted is False
        assert info.compressed_size >= 0
        assert info.uncompressed_size > 0

    def test_tar_info(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("hello")
        p = tmp_path / "test.tar"
        with tarfile.open(p, "w") as tf:
            tf.add(src, arcname="src")
        info = get_archive_info(p)
        assert info.format_name == "TAR"
        assert info.file_count > 0
        assert info.is_encrypted is False
        assert info.archive_path == p

    def test_zip_ratio(self, tmp_path):
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.txt", "A" * 10_000)
        info = get_archive_info(p)
        assert info.uncompressed_size == 10_000
        assert 0 <= info.compressed_size <= info.uncompressed_size

    def test_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            get_archive_info(tmp_path / "missing.zip")
