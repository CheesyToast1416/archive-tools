"""Edge-case tests: path traversal, empty archives, corrupt data, batch isolation."""

from __future__ import annotations

import zipfile
from pathlib import Path

from archivetools.operations import (
    ArchiveStructure,
    StructureKind,
    analyze_structure,
    extract_archive,
    list_archive,
)
from archivetools.operations.extract import smart_restructure

# ── ZipSlip / path-traversal ──────────────────────────────────────────────────


class TestPathTraversal:
    def test_dotdot_entry_stays_inside_destination(self, tmp_path: Path) -> None:
        p = tmp_path / "evil.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr(zipfile.ZipInfo("../../evil.txt"), "pwned")
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = extract_archive(
            p, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert ok
        assert not (tmp_path.parent / "evil.txt").exists()

    def test_absolute_path_entry_sandboxed(self, tmp_path: Path) -> None:
        p = tmp_path / "abs.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr(zipfile.ZipInfo("/etc/evil.conf"), "bad")
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = extract_archive(
            p, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert ok
        assert not (
            Path("/etc/evil.conf").exists()
            and Path("/etc/evil.conf").read_text() == "bad"
        )


# ── Empty archive ─────────────────────────────────────────────────────────────


class TestEmptyArchive:
    def test_extract_empty_zip_succeeds(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.zip"
        with zipfile.ZipFile(p, "w"):
            pass
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = extract_archive(
            p, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert ok
        assert list(out.iterdir()) == []

    def test_list_empty_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.zip"
        with zipfile.ZipFile(p, "w"):
            pass
        ok, _, names = list_archive(p, "")
        assert ok
        assert names == []

    def test_analyze_empty_names(self) -> None:
        assert analyze_structure([]).kind == StructureKind.EMPTY
        assert analyze_structure(["", "/"]).kind == StructureKind.EMPTY

    def test_smart_restructure_empty_noop(self, tmp_path: Path) -> None:
        smart_restructure(tmp_path, ArchiveStructure(kind=StructureKind.EMPTY))


# ── Corrupt archive ───────────────────────────────────────────────────────────


class TestCorruptArchive:
    def test_truncated_zip_list_returns_not_ok(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.zip"
        p.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
        ok, _, names = list_archive(p, "")
        assert not ok
        assert names == []

    def test_garbage_file_list_returns_not_ok(self, tmp_path: Path) -> None:
        p = tmp_path / "garbage.zip"
        p.write_bytes(b"\x00\x01\x02\x03" * 100)
        ok, _, names = list_archive(p, "")
        assert not ok

    def test_extract_corrupt_zip_returns_false(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.zip"
        p.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = extract_archive(
            p, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert not ok

    def test_verify_corrupt_zip_returns_bool(self, tmp_path: Path) -> None:
        from archivetools.operations import test_archive as verify

        p = tmp_path / "corrupt.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("f.txt", "hello world " * 50)
        data = bytearray(p.read_bytes())
        mid = len(data) // 2
        data[mid] ^= 0xFF
        data[mid + 1] ^= 0xFF
        p.write_bytes(bytes(data))
        ok, failed = verify(p)
        assert isinstance(ok, bool)
        assert isinstance(failed, list)


# ── Batch failure isolation ────────────────────────────────────────────────────


class TestBatchFailureIsolation:
    def test_bad_archive_does_not_prevent_good_one(self, tmp_path: Path) -> None:
        good = tmp_path / "good.zip"
        with zipfile.ZipFile(good, "w") as zf:
            zf.writestr("ok.txt", "content")
        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"not a zip")
        out = tmp_path / "out"
        out.mkdir()

        results = []
        for archive in [bad, good]:
            _, _, names = list_archive(archive, "")
            ok, _ = extract_archive(
                archive,
                "",
                str(out),
                filename_encoding=None,
                password_encoding=None,
                names=names,
                smart=True,
            )
            results.append(ok)

        assert results[0] is False
        assert results[1] is True
        assert (out / "ok.txt").exists()


# ── Smart restructure edge cases ──────────────────────────────────────────────


class TestSmartRestructureEdgeCases:
    def test_wrapper_not_on_disk_noop(self, tmp_path: Path) -> None:
        s = ArchiveStructure(
            kind=StructureKind.SINGLE_DIR, top_dir="ghost", top_dir_child_count=1
        )
        smart_restructure(tmp_path, s)
        assert list(tmp_path.iterdir()) == []

    def test_extra_hidden_file_blocks_unwrap(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "file.txt").write_text("a")
        (wrapper / ".hidden").write_text("b")
        s = ArchiveStructure(
            kind=StructureKind.SINGLE_DIR, top_dir="wrapper", top_dir_child_count=1
        )
        smart_restructure(tmp_path, s)
        assert (wrapper / "file.txt").exists()
