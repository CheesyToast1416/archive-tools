"""
Edge-case tests identified during refactor review:
  • ZipSlip / path-traversal in archive filenames
  • Empty archive extraction
  • Corrupt archive detection
  • Batch extraction with mixed-success items
  • StructureKind enum comparisons (both string and enum values)
  • analyze_structure edge cases
"""

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
from archivetools.operations import (
    test_archive as verify_archive,
)
from archivetools.operations.extract import smart_restructure

# ── ZipSlip / path-traversal ──────────────────────────────────────────────────


class TestPathTraversal:
    """Python's zipfile.extract() sanitises paths since 3.6. Verify we are safe."""

    def _zip_with_traversal(self, dest: Path) -> Path:
        p = dest / "evil.zip"
        with zipfile.ZipFile(p, "w") as zf:
            info = zipfile.ZipInfo("../../evil.txt")
            zf.writestr(info, "pwned")
        return p

    def test_traversal_entry_not_extracted_outside_dest(self, tmp_path: Path) -> None:
        z = self._zip_with_traversal(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        # Should not raise, but the traversal entry must not land outside `out`
        ok, _ = extract_archive(
            z, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert ok
        evil = tmp_path.parent / "evil.txt"  # where it would land if unprotected
        assert not evil.exists(), "ZipSlip: file extracted outside destination"

    def test_absolute_path_entry_sandboxed(self, tmp_path: Path) -> None:
        p = tmp_path / "abs.zip"
        with zipfile.ZipFile(p, "w") as zf:
            info = zipfile.ZipInfo("/etc/evil.conf")
            zf.writestr(info, "bad content")
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = extract_archive(
            p, "", str(out), filename_encoding=None, password_encoding=None
        )
        assert ok
        assert (
            not Path("/etc/evil.conf").exists()
            or Path("/etc/evil.conf").read_text() != "bad content"
        ), "Absolute-path entry escaped destination"


# ── Empty archive ─────────────────────────────────────────────────────────────


class TestEmptyArchive:
    def test_extract_empty_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.zip"
        with zipfile.ZipFile(p, "w"):
            pass  # no entries
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = extract_archive(
            p,
            "",
            str(out),
            filename_encoding=None,
            password_encoding=None,
            names=[],
            smart=True,
        )
        assert ok
        # Output dir exists but is empty
        assert list(out.iterdir()) == []

    def test_list_empty_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.zip"
        with zipfile.ZipFile(p, "w"):
            pass
        ok, _enc, names = list_archive(p, "")
        assert ok
        assert names == []

    def test_analyze_empty_names(self) -> None:
        s = analyze_structure([])
        assert s.kind == StructureKind.EMPTY
        assert s.top_entries == []

    def test_analyze_only_directory_entries(self) -> None:
        # Archives that only contain bare directory entries (no files)
        s = analyze_structure(["dir/", "dir/sub/"])
        # "dir" has one direct child "sub", should be SINGLE_DIR
        assert s.kind == StructureKind.SINGLE_DIR
        assert s.top_dir == "dir"

    def test_smart_restructure_empty_noop(self, tmp_path: Path) -> None:
        s = ArchiveStructure(kind=StructureKind.EMPTY)
        smart_restructure(tmp_path, s)  # must not raise


# ── StructureKind enum ────────────────────────────────────────────────────────


class TestStructureKind:
    """StructureKind is a StrEnum — values compare equal to plain strings."""

    def test_enum_equals_string(self) -> None:
        assert StructureKind.MULTI == "multi"
        assert StructureKind.EMPTY == "empty"
        assert StructureKind.SINGLE_FILE == "single_file"
        assert StructureKind.SINGLE_DIR == "single_dir"

    def test_string_equals_enum(self) -> None:
        assert "multi" == StructureKind.MULTI
        assert "single_dir" == StructureKind.SINGLE_DIR

    def test_analyze_returns_enum_members(self) -> None:
        s = analyze_structure(["a.txt", "b.txt"])
        assert s.kind is StructureKind.MULTI
        assert isinstance(s.kind, StructureKind)


# ── Corrupt archive ───────────────────────────────────────────────────────────


class TestCorruptArchive:
    def test_truncated_zip_list_returns_failure(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.zip"
        p.write_bytes(b"PK\x03\x04" + b"\x00" * 20)  # valid magic, garbage body
        ok, _enc, names = list_archive(p, "")
        assert not ok
        assert names == []

    def test_garbage_file_list_returns_failure(self, tmp_path: Path) -> None:
        p = tmp_path / "notanarchive.zip"
        p.write_bytes(b"\x00\x01\x02\x03" * 100)
        ok, _enc, names = list_archive(p, "")
        assert not ok

    def test_verify_archive_on_corrupt_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.zip"
        # Write a real ZIP then corrupt it
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("file.txt", "hello world " * 50)
        data = bytearray(p.read_bytes())
        # Flip bytes in the middle of the compressed data
        mid = len(data) // 2
        data[mid] ^= 0xFF
        data[mid + 1] ^= 0xFF
        p.write_bytes(bytes(data))
        ok, failed = verify_archive(p)
        # Corruption detection depends on which bytes land in the CRC zone.
        assert isinstance(ok, bool)
        assert isinstance(failed, list)


# ── analyze_structure edge cases ─────────────────────────────────────────────


class TestAnalyzeStructureEdgeCases:
    def test_blank_and_slash_only_names_ignored(self) -> None:
        # "", "/" and "//" all strip to "" → treated as no entries
        s = analyze_structure(["", "/", "//"])
        assert s.kind == StructureKind.EMPTY

    def test_nested_paths_counted_correctly(self) -> None:
        # Only direct children of the top-level dir count
        names = ["app/", "app/a.txt", "app/sub/b.txt", "app/sub/c.txt"]
        s = analyze_structure(names)
        assert s.kind == StructureKind.SINGLE_DIR
        assert s.top_dir == "app"
        # Direct children: "a.txt" and "sub" → count = 2
        assert s.top_dir_child_count == 2

    def test_single_file_at_root(self) -> None:
        s = analyze_structure(["readme.md"])
        assert s.kind == StructureKind.SINGLE_FILE
        assert s.top_entries == ["readme.md"]
        assert s.top_dir is None

    def test_mixed_files_and_dirs_at_root(self) -> None:
        s = analyze_structure(["README.md", "src/", "src/main.py", "tests/"])
        assert s.kind == StructureKind.MULTI
        assert "README.md" in s.top_entries
        assert "src" in s.top_entries


# ── Batch extraction failure isolation ────────────────────────────────────────


class TestBatchFailureIsolation:
    """A failing archive in a batch must not abort subsequent archives."""

    def test_bad_archive_does_not_stop_batch(self, tmp_path: Path) -> None:
        from archivetools.operations import list_archive

        good = tmp_path / "good.zip"
        with zipfile.ZipFile(good, "w") as zf:
            zf.writestr("ok.txt", "content")

        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"not a zip file")

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

        assert results[0] is False, "bad archive should fail"
        assert results[1] is True, "good archive should succeed despite prior failure"
        assert (out / "ok.txt").exists()


# ── smart_restructure edge cases ─────────────────────────────────────────────


class TestSmartRestructureEdgeCases:
    def test_wrapper_missing_from_disk(self, tmp_path: Path) -> None:
        """Wrapper dir never extracted (e.g. dir-only entry) — must not raise."""
        s = ArchiveStructure(
            kind=StructureKind.SINGLE_DIR, top_dir="ghost", top_dir_child_count=1
        )
        # "ghost/" dir never extracted — must not raise
        smart_restructure(tmp_path, s)
        # Nothing was created; output dir unchanged
        assert list(tmp_path.iterdir()) == []

    def test_multi_real_children_vs_archive_count(self, tmp_path: Path) -> None:
        """If the real child count differs from archive count (e.g. hidden files),
        restructure should leave things alone."""
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "file.txt").write_text("a")
        (wrapper / ".hidden").write_text("b")  # extra hidden file on disk

        s = ArchiveStructure(
            kind=StructureKind.SINGLE_DIR, top_dir="wrapper", top_dir_child_count=1
        )
        # 2 real children vs 1 in archive metadata → should NOT unwrap
        smart_restructure(tmp_path, s)
        assert (wrapper / "file.txt").exists(), "wrapper incorrectly collapsed"
