from __future__ import annotations

import tarfile
import zipfile

import pytest

from archivetools.operations import test_archive as verify_archive


def _make_zip(tmp_path, n_files=3, password=None):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as zf:
        for i in range(n_files):
            zf.writestr(f"file{i}.txt", f"content {i}" * 100)
    return p


def _make_tar(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    (src / "b.txt").write_text("world")
    p = tmp_path / "test.tar"
    with tarfile.open(p, "w") as tf:
        tf.add(src, arcname="src")
    return p


class TestTestArchive:
    def test_good_zip(self, tmp_path):
        archive = _make_zip(tmp_path)
        ok, failed = verify_archive(archive)
        assert ok is True
        assert failed == []

    def test_good_tar(self, tmp_path):
        archive = _make_tar(tmp_path)
        ok, failed = verify_archive(archive)
        assert ok is True

    def test_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            verify_archive(tmp_path / "missing.zip")

    def test_wrong_password_zip(self, tmp_path):
        # A plain (unencrypted) ZIP with wrong password still passes —
        # the password is ignored for unencrypted entries.
        archive = _make_zip(tmp_path)
        ok, failed = verify_archive(archive, "wrongpass")
        assert ok is True  # no encrypted entries

    def test_zip_bad_password_encrypted(self, tmp_path):
        import pyzipper

        p = tmp_path / "enc.zip"
        with pyzipper.AESZipFile(p, "w", encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(b"secret")
            zf.writestr("file.txt", "hello world")
        ok, failed = verify_archive(p, "wrongpassword")
        assert ok is False
