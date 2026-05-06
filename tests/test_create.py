from __future__ import annotations

import tarfile
import zipfile

import pytest

from archivetools.operations import create_archive


def _make_src(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("world")
    (src / "data.csv").write_text("a,b,c")
    return src


class TestCreateZip:
    def test_create_plain(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.zip"
        ok = create_archive(out, [src], format="zip")
        assert ok is True
        assert out.exists()
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert any("hello.txt" in n for n in names)
        assert any("data.csv" in n for n in names)

    def test_create_single_file(self, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("hello")
        out = tmp_path / "out.zip"
        ok = create_archive(out, [f], format="zip")
        assert ok is True
        with zipfile.ZipFile(out) as zf:
            assert "note.txt" in zf.namelist()

    def test_password_raises(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="AES"):
            create_archive(tmp_path / "out.zip", [f], format="zip", password="pw")

    def test_create_aes(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.zip"
        ok = create_archive(out, [src], format="zip-aes", password="secret")
        assert ok is True
        assert out.exists()
        # Verify it can be read back with pyzipper
        import pyzipper

        with pyzipper.AESZipFile(out) as zf:
            zf.setpassword(b"secret")
            names = zf.namelist()
        assert any("hello.txt" in n for n in names)


class TestCreateTar:
    def test_create_tar(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.tar"
        ok = create_archive(out, [src], format="tar")
        assert ok is True
        with tarfile.open(out) as tf:
            names = tf.getnames()
        assert any("hello.txt" in n for n in names)

    def test_create_tar_gz(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.tar.gz"
        ok = create_archive(out, [src], format="tar.gz")
        assert ok is True
        with tarfile.open(out, "r:gz") as tf:
            names = tf.getnames()
        assert any("hello.txt" in n for n in names)

    def test_create_tar_bz2(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.tar.bz2"
        ok = create_archive(out, [src], format="tar.bz2")
        assert ok is True
        with tarfile.open(out, "r:bz2") as tf:
            assert len(tf.getnames()) > 0

    def test_create_tar_xz(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.tar.xz"
        ok = create_archive(out, [src], format="tar.xz")
        assert ok is True
        with tarfile.open(out, "r:xz") as tf:
            assert len(tf.getnames()) > 0

    def test_password_raises(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("x")
        with pytest.raises(TypeError, match="encryption"):
            create_archive(tmp_path / "out.tar", [f], format="tar", password="pw")


class TestCreateSevenZip:
    def test_create_7z(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.7z"
        ok = create_archive(out, [src], format="7z")
        assert ok is True
        import py7zr

        with py7zr.SevenZipFile(str(out), mode="r") as sz:
            names = sz.getnames()
        assert any("hello.txt" in n for n in names)

    def test_create_7z_encrypted(self, tmp_path):
        src = _make_src(tmp_path)
        out = tmp_path / "archive.7z"
        ok = create_archive(out, [src], format="7z", password="pw123")
        assert ok is True
        import py7zr

        with py7zr.SevenZipFile(str(out), mode="r", password="pw123") as sz:
            names = sz.getnames()
        assert any("hello.txt" in n for n in names)


class TestCreateErrors:
    def test_unsupported_format(self, tmp_path):
        with pytest.raises(ValueError, match="Unsupported format"):
            create_archive(tmp_path / "out.rar", [], format="rar")
