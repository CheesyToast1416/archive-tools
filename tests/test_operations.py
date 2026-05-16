"""Tests for the operations layer: extract, create, convert, update, verify, inspect.

Consolidates: test_create.py, test_convert.py, test_batch.py, test_test_archive.py
New coverage: update_archive (ZIP, 7z, TAR)
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from archivetools.operations import (
    convert_archive,
    create_archive,
    detect_archive_encoding,
    get_archive_info,
    list_archive,
    update_archive,
)
from archivetools.operations import (
    test_archive as verify_archive,
)
from archivetools.operations.extract import extract_archive

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_zip(path: Path, entries: dict[str, str] | None = None) -> Path:
    entries = entries or {"hello.txt": "content", "data.csv": "a,b"}
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


def _make_tar(path: Path, entries: dict[str, bytes] | None = None) -> Path:
    import time as _time

    entries = entries or {"hello.txt": b"content", "data.csv": b"a,b"}
    ext = str(path)
    mode = (
        "w:gz"
        if ext.endswith(".gz")
        else "w:bz2"
        if ext.endswith(".bz2")
        else "w:xz"
        if ext.endswith(".xz")
        else "w"
    )
    with tarfile.open(path, mode) as tf:
        for name, data in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = int(_time.time())  # ZIP requires timestamps >= 1980
            tf.addfile(info, io.BytesIO(data))
    return path


def _make_src(tmp_path: Path) -> Path:
    d = tmp_path / "src"
    d.mkdir()
    (d / "hello.txt").write_text("world")
    (d / "data.csv").write_text("a,b,c")
    return d


# ── extract_archive ────────────────────────────────────────────────────────────


class TestExtractArchive:
    def test_extracts_zip_to_output_dir(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "a.zip")
        out = tmp_path / "out"
        ok, _ = extract_archive(
            z, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert ok is True
        assert (out / "hello.txt").exists()

    def test_missing_archive_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_archive(
                tmp_path / "nope.zip",
                "",
                None,
                filename_encoding=None,
                password_encoding=None,
            )

    def test_progress_callback_receives_monotonic_values(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "a.zip", {f"f{i}.txt": "x" for i in range(5)})
        out = tmp_path / "out"
        calls: list[int] = []
        ok, _ = extract_archive(
            z,
            "",
            str(out),
            filename_encoding=None,
            password_encoding=None,
            progress=lambda c, t, f: calls.append(c),
        )
        assert ok is True
        assert calls == list(range(1, 6))

    def test_smart_extraction_single_dir_no_double_wrap(self, tmp_path: Path) -> None:
        # myapp.zip → myapp/file1.txt, myapp/file2.txt; smart extracts to out/myapp/
        z = _make_zip(
            tmp_path / "myapp.zip", {"myapp/file1.txt": "x", "myapp/file2.txt": "y"}
        )
        out = tmp_path / "out"
        _, _, names = list_archive(z, "")
        ok, _ = extract_archive(
            z,
            "",
            str(out),
            filename_encoding=None,
            password_encoding=None,
            names=names,
            smart=True,
        )
        assert ok is True
        assert (out / "myapp" / "file1.txt").exists()
        assert not (out / "myapp" / "myapp").exists(), "double-nesting still present"

    def test_smart_extraction_single_child_unwraps(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "wrap.zip", {"wrapper/only.txt": "x"})
        out = tmp_path / "out"
        _, _, names = list_archive(z, "")
        ok, _ = extract_archive(
            z,
            "",
            str(out),
            filename_encoding=None,
            password_encoding=None,
            names=names,
            smart=True,
        )
        assert ok is True
        assert (out / "only.txt").exists()
        assert not (out / "wrapper").exists()

    def test_smart_extraction_multi_creates_wrapper_dir(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "files.zip", {"file1.txt": "a", "file2.txt": "b"})
        out = tmp_path / "out"
        _, _, names = list_archive(z, "")
        ok, _ = extract_archive(
            z,
            "",
            str(out),
            filename_encoding=None,
            password_encoding=None,
            names=names,
            smart=True,
        )
        assert ok is True
        assert (out / "files" / "file1.txt").exists()

    def test_bad_archive_returns_false(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"not a zip")
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = extract_archive(
            bad, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert ok is False


# ── create_archive ────────────────────────────────────────────────────────────


class TestCreateArchive:
    def test_create_zip_plain(self, tmp_path: Path) -> None:
        src = _make_src(tmp_path)
        out = tmp_path / "out.zip"
        assert create_archive(out, [src], format="zip") is True
        with zipfile.ZipFile(out) as zf:
            assert any("hello.txt" in n for n in zf.namelist())

    def test_create_zip_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "note.txt"
        f.write_text("hi")
        out = tmp_path / "out.zip"
        create_archive(out, [f], format="zip")
        with zipfile.ZipFile(out) as zf:
            assert "note.txt" in zf.namelist()

    def test_create_zip_plain_rejects_password(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="AES"):
            create_archive(tmp_path / "out.zip", [f], format="zip", password="pw")

    def test_create_zip_aes(self, tmp_path: Path) -> None:
        import pyzipper

        src = _make_src(tmp_path)
        out = tmp_path / "out.zip"
        assert create_archive(out, [src], format="zip-aes", password="secret") is True
        with pyzipper.AESZipFile(out) as zf:
            zf.setpassword(b"secret")
            assert any("hello.txt" in n for n in zf.namelist())

    def test_create_tar(self, tmp_path: Path) -> None:
        src = _make_src(tmp_path)
        out = tmp_path / "out.tar"
        assert create_archive(out, [src], format="tar") is True
        with tarfile.open(out) as tf:
            assert any("hello.txt" in n for n in tf.getnames())

    def test_create_tar_gz(self, tmp_path: Path) -> None:
        src = _make_src(tmp_path)
        out = tmp_path / "out.tar.gz"
        assert create_archive(out, [src], format="tar.gz") is True
        with tarfile.open(out, "r:gz") as tf:
            assert len(tf.getnames()) > 0

    def test_create_tar_bz2(self, tmp_path: Path) -> None:
        src = _make_src(tmp_path)
        out = tmp_path / "out.tar.bz2"
        assert create_archive(out, [src], format="tar.bz2") is True

    def test_create_tar_xz(self, tmp_path: Path) -> None:
        src = _make_src(tmp_path)
        out = tmp_path / "out.tar.xz"
        assert create_archive(out, [src], format="tar.xz") is True

    def test_create_tar_rejects_password(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("x")
        with pytest.raises(TypeError, match="encryption"):
            create_archive(tmp_path / "out.tar", [f], format="tar", password="pw")

    def test_create_7z(self, tmp_path: Path) -> None:
        import py7zr

        src = _make_src(tmp_path)
        out = tmp_path / "out.7z"
        assert create_archive(out, [src], format="7z") is True
        with py7zr.SevenZipFile(str(out), "r") as sz:
            assert any("hello.txt" in n for n in sz.getnames())

    def test_create_7z_encrypted(self, tmp_path: Path) -> None:
        import py7zr

        src = _make_src(tmp_path)
        out = tmp_path / "out.7z"
        assert create_archive(out, [src], format="7z", password="pw123") is True
        with py7zr.SevenZipFile(str(out), "r", password="pw123") as sz:
            assert len(sz.getnames()) > 0

    def test_unsupported_format_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            create_archive(tmp_path / "out.rar", [], format="rar")


# ── convert_archive ────────────────────────────────────────────────────────────


class TestConvertArchive:
    def test_zip_to_zip(self, tmp_path: Path) -> None:
        src = _make_zip(tmp_path / "src.zip")
        out = tmp_path / "out.zip"
        assert convert_archive(src, out, "zip") is True
        with zipfile.ZipFile(out) as zf:
            assert any("hello.txt" in n for n in zf.namelist())

    def test_zip_to_tar_gz(self, tmp_path: Path) -> None:
        src = _make_zip(tmp_path / "src.zip")
        out = tmp_path / "out.tar.gz"
        assert convert_archive(src, out, "tar.gz") is True
        with tarfile.open(out, "r:gz") as tf:
            assert any("hello.txt" in n for n in tf.getnames())

    def test_zip_to_7z(self, tmp_path: Path) -> None:
        import py7zr

        src = _make_zip(tmp_path / "src.zip")
        out = tmp_path / "out.7z"
        assert convert_archive(src, out, "7z") is True
        with py7zr.SevenZipFile(str(out), "r") as sz:
            assert any("hello.txt" in n for n in sz.getnames())

    def test_zip_to_zip_aes_with_password(self, tmp_path: Path) -> None:
        import pyzipper

        src = _make_zip(tmp_path / "src.zip")
        out = tmp_path / "out.zip"
        assert convert_archive(src, out, "zip-aes", output_password="secret") is True
        with pyzipper.AESZipFile(out) as zf:
            zf.setpassword(b"secret")
            assert len(zf.namelist()) > 0

    def test_tar_to_zip(self, tmp_path: Path) -> None:
        src = _make_tar(tmp_path / "src.tar")
        out = tmp_path / "out.zip"
        assert convert_archive(src, out, "zip") is True
        with zipfile.ZipFile(out) as zf:
            assert len(zf.namelist()) > 0

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            convert_archive(tmp_path / "missing.zip", tmp_path / "out.zip", "zip")

    def test_unsupported_output_format_raises(self, tmp_path: Path) -> None:
        src = _make_zip(tmp_path / "src.zip")
        with pytest.raises(ValueError):
            convert_archive(src, tmp_path / "out.rar", "rar")


# ── update_archive ────────────────────────────────────────────────────────────


class TestUpdateArchiveZip:
    def test_add_file_to_zip(self, tmp_path: Path) -> None:
        archive = _make_zip(tmp_path / "a.zip")
        new_file = tmp_path / "extra.txt"
        new_file.write_text("extra content")
        assert update_archive(archive, files_to_add=[new_file]) is True
        with zipfile.ZipFile(archive) as zf:
            assert "extra.txt" in zf.namelist()
            assert "hello.txt" in zf.namelist()

    def test_remove_entry_from_zip(self, tmp_path: Path) -> None:
        archive = _make_zip(
            tmp_path / "a.zip", {"keep.txt": "keep", "drop.txt": "drop"}
        )
        assert update_archive(archive, paths_to_remove=["drop.txt"]) is True
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        assert "keep.txt" in names
        assert "drop.txt" not in names

    def test_add_and_remove_simultaneously(self, tmp_path: Path) -> None:
        archive = _make_zip(tmp_path / "a.zip", {"old.txt": "old", "keep.txt": "keep"})
        new_file = tmp_path / "new.txt"
        new_file.write_text("new")
        update_archive(archive, files_to_add=[new_file], paths_to_remove=["old.txt"])
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        assert "new.txt" in names
        assert "keep.txt" in names
        assert "old.txt" not in names

    def test_no_ops_returns_true(self, tmp_path: Path) -> None:
        archive = _make_zip(tmp_path / "a.zip")
        assert update_archive(archive) is True

    def test_rar_raises_not_implemented(self, tmp_path: Path) -> None:
        p = tmp_path / "a.rar"
        p.write_bytes(b"Rar!\x1a\x07\x00")
        with pytest.raises(NotImplementedError):
            update_archive(p, files_to_add=[tmp_path / "x.txt"])


class TestUpdateArchive7z:
    @pytest.fixture
    def archive_7z(self, tmp_path: Path) -> Path:
        import py7zr

        # Use real files to avoid py7zr permission quirks with writestr-extracted files
        src = tmp_path / "src"
        src.mkdir()
        (src / "keep.txt").write_text("keep")
        (src / "drop.txt").write_text("drop")
        p = tmp_path / "arch.7z"
        with py7zr.SevenZipFile(p, "w") as sz:
            for f in src.iterdir():
                sz.write(str(f), f.name)
        return p

    def test_add_file_to_7z(self, archive_7z: Path, tmp_path: Path) -> None:
        new_file = tmp_path / "extra.txt"
        new_file.write_text("extra")
        assert update_archive(archive_7z, files_to_add=[new_file]) is True
        import py7zr

        with py7zr.SevenZipFile(archive_7z, "r") as sz:
            assert "extra.txt" in sz.getnames()

    def test_remove_entry_from_7z(self, archive_7z: Path) -> None:
        assert update_archive(archive_7z, paths_to_remove=["drop.txt"]) is True
        import py7zr

        with py7zr.SevenZipFile(archive_7z, "r") as sz:
            names = sz.getnames()
        assert "keep.txt" in names
        assert "drop.txt" not in names


class TestUpdateArchiveTar:
    @pytest.fixture
    def archive_tar(self, tmp_path: Path) -> Path:
        return _make_tar(
            tmp_path / "arch.tar", {"keep.txt": b"keep", "drop.txt": b"drop"}
        )

    def test_remove_entry_from_tar(self, archive_tar: Path) -> None:
        assert update_archive(archive_tar, paths_to_remove=["drop.txt"]) is True
        with tarfile.open(archive_tar) as tf:
            names = tf.getnames()
        assert "keep.txt" in names
        assert "drop.txt" not in names

    def test_add_file_to_tar(self, archive_tar: Path, tmp_path: Path) -> None:
        new_file = tmp_path / "extra.txt"
        new_file.write_text("extra")
        assert update_archive(archive_tar, files_to_add=[new_file]) is True
        with tarfile.open(archive_tar) as tf:
            assert "extra.txt" in tf.getnames()


# ── test_archive (integrity verify) ───────────────────────────────────────────


class TestVerifyArchive:
    def test_valid_zip_passes(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "a.zip")
        ok, failed = verify_archive(z)
        assert ok is True
        assert failed == []

    def test_valid_tar_passes(self, simple_tar: Path) -> None:
        ok, failed = verify_archive(simple_tar)
        assert ok is True

    def test_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            verify_archive(tmp_path / "missing.zip")

    def test_unencrypted_zip_with_any_password_passes(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "a.zip")
        ok, failed = verify_archive(z, "wrongpass")
        assert ok is True  # password ignored for unencrypted

    def test_encrypted_zip_wrong_password_fails(self, tmp_path: Path) -> None:
        import pyzipper

        p = tmp_path / "enc.zip"
        with pyzipper.AESZipFile(p, "w", encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(b"secret")
            zf.writestr("f.txt", "hello world " * 20)
        ok, failed = verify_archive(p, "wrongpassword")
        assert ok is False

    def test_encrypted_zip_correct_password_passes(self, tmp_path: Path) -> None:
        import pyzipper

        p = tmp_path / "enc.zip"
        with pyzipper.AESZipFile(p, "w", encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(b"secret")
            zf.writestr("f.txt", "hello world " * 20)
        ok, _ = verify_archive(p, "secret")
        assert ok is True


# ── inspect (list + info + detect_encoding) ────────────────────────────────────


class TestListArchive:
    def test_list_simple_zip(self, simple_zip: Path) -> None:
        ok, enc, names = list_archive(simple_zip, "")
        assert ok is True
        assert "hello.txt" in names
        assert "subdir/nested.txt" in names

    def test_list_empty_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.zip"
        with zipfile.ZipFile(p, "w"):
            pass
        ok, _, names = list_archive(p, "")
        assert ok is True
        assert names == []

    def test_list_tar(self, simple_tar: Path) -> None:
        ok, enc, names = list_archive(simple_tar, "")
        assert ok is True
        assert enc is None
        assert "hello.txt" in names

    def test_list_corrupt_zip_returns_not_ok(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.zip"
        p.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
        ok, _, names = list_archive(p, "")
        assert ok is False

    def test_list_aes_zip_names_visible_without_password(
        self, encrypted_zip: Path
    ) -> None:
        ok, _, names = list_archive(encrypted_zip, "wrong_password")
        assert ok is True  # AES-ZIP names are always readable
        assert "secret.txt" in names


class TestGetArchiveInfo:
    def test_zip_info(self, simple_zip: Path) -> None:
        info = get_archive_info(simple_zip)
        assert info.format_name == "ZIP"
        assert info.file_count == 2
        assert info.is_encrypted is False
        assert info.compressed_size > 0
        assert info.uncompressed_size > 0

    def test_tar_info(self, simple_tar: Path) -> None:
        info = get_archive_info(simple_tar)
        assert info.format_name == "TAR"
        assert info.file_count >= 2
        assert info.is_encrypted is False

    def test_compressed_size_leq_uncompressed(self, tmp_path: Path) -> None:
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.txt", "A" * 10_000)
        info = get_archive_info(p)
        assert info.uncompressed_size == 10_000
        assert info.compressed_size <= info.uncompressed_size

    def test_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            get_archive_info(tmp_path / "missing.zip")


class TestDetectArchiveEncoding:
    def test_utf8_zip_returns_none_or_utf8(self, simple_zip: Path) -> None:
        enc, conf = detect_archive_encoding(simple_zip)
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    def test_tar_returns_none_encoding(self, simple_tar: Path) -> None:
        enc, conf = detect_archive_encoding(simple_tar)
        assert enc is None
        assert conf == 0.0
