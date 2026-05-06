from __future__ import annotations

import tarfile

import pytest

from archivetools.formats.tar import TarHandler


class TestTarHandler:
    def _make_tar(self, tmp_path, compression=""):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("world")
        (src / "data.csv").write_text("a,b,c")

        ext = {"": ".tar", "gz": ".tar.gz", "bz2": ".tar.bz2", "xz": ".tar.xz"}[compression]
        archive = tmp_path / f"test{ext}"
        mode = f"w:{compression}" if compression else "w"
        with tarfile.open(archive, mode) as tf:
            tf.add(src, arcname="src")
        return archive

    def test_list_contents(self, tmp_path):
        archive = self._make_tar(tmp_path)
        handler = TarHandler()
        ok, enc, names = handler.list_contents(archive, "")
        assert ok is True
        assert enc is None
        assert any("hello.txt" in n for n in names)

    def test_extract(self, tmp_path):
        archive = self._make_tar(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        handler = TarHandler()
        ok, enc = handler.extract(archive, "", out)
        assert ok is True
        assert (out / "src" / "hello.txt").exists()

    def test_extract_gz(self, tmp_path):
        archive = self._make_tar(tmp_path, "gz")
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = TarHandler().extract(archive, "", out)
        assert ok is True

    def test_password_raises(self, tmp_path):
        archive = self._make_tar(tmp_path)
        with pytest.raises(TypeError, match="do not support encryption"):
            TarHandler().extract(archive, "somepassword", tmp_path / "out")

    def test_get_info(self, tmp_path):
        archive = self._make_tar(tmp_path)
        info = TarHandler().get_info(archive)
        assert info.format_name == "TAR"
        assert info.file_count > 0
        assert info.is_encrypted is False
