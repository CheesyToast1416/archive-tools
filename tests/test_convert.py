from __future__ import annotations

import tarfile
import zipfile

import pytest

from archivetools.operations import convert_archive


def _make_zip(tmp_path, files=("hello.txt", "data.csv")):
    p = tmp_path / "source.zip"
    with zipfile.ZipFile(p, "w") as zf:
        for name in files:
            zf.writestr(name, f"content of {name}")
    return p


def _make_tar(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    p = tmp_path / "source.tar"
    with tarfile.open(p, "w") as tf:
        tf.add(src, arcname="src")
    return p


class TestConvertArchive:
    def test_zip_to_zip(self, tmp_path):
        src = _make_zip(tmp_path)
        out = tmp_path / "out.zip"
        ok = convert_archive(src, out, "zip")
        assert ok is True
        assert out.exists()
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert any("hello.txt" in n for n in names)

    def test_zip_to_tar_gz(self, tmp_path):
        src = _make_zip(tmp_path)
        out = tmp_path / "out.tar.gz"
        ok = convert_archive(src, out, "tar.gz")
        assert ok is True
        with tarfile.open(out, "r:gz") as tf:
            names = tf.getnames()
        assert any("hello.txt" in n for n in names)

    def test_zip_to_7z(self, tmp_path):
        src = _make_zip(tmp_path)
        out = tmp_path / "out.7z"
        ok = convert_archive(src, out, "7z")
        assert ok is True
        import py7zr

        with py7zr.SevenZipFile(str(out), mode="r") as sz:
            names = sz.getnames()
        assert any("hello.txt" in n for n in names)

    def test_tar_to_zip(self, tmp_path):
        src = _make_tar(tmp_path)
        out = tmp_path / "out.zip"
        ok = convert_archive(src, out, "zip")
        assert ok is True
        with zipfile.ZipFile(out) as zf:
            assert len(zf.namelist()) > 0

    def test_zip_to_zip_aes_with_password(self, tmp_path):
        src = _make_zip(tmp_path)
        out = tmp_path / "out.zip"
        ok = convert_archive(src, out, "zip-aes", output_password="secret")
        assert ok is True
        import pyzipper

        with pyzipper.AESZipFile(out) as zf:
            zf.setpassword(b"secret")
            names = zf.namelist()
        assert any("hello.txt" in n for n in names)

    def test_nonexistent_source_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            convert_archive(tmp_path / "missing.zip", tmp_path / "out.zip", "zip")

    def test_unsupported_format(self, tmp_path):
        src = _make_zip(tmp_path)
        with pytest.raises(ValueError):
            convert_archive(src, tmp_path / "out.rar", "rar")
