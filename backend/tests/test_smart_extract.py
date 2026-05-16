"""Tests for smart extraction logic:
structure analysis, output-dir selection, restructure.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from archivetools.operations.extract import (
    ArchiveStructure,
    StructureKind,
    _archive_stem,
    analyze_structure,
    smart_output_dir,
    smart_restructure,
)


class TestAnalyzeStructure:
    def test_empty_list(self) -> None:
        assert analyze_structure([]).kind == StructureKind.EMPTY

    def test_blank_slash_entries_treated_as_empty(self) -> None:
        assert analyze_structure(["", "/", "//"]).kind == StructureKind.EMPTY

    def test_single_file_at_root(self) -> None:
        s = analyze_structure(["readme.txt"])
        assert s.kind == StructureKind.SINGLE_FILE
        assert s.top_entries == ["readme.txt"]
        assert s.top_dir is None

    def test_single_dir_multi_children(self) -> None:
        names = ["myapp/", "myapp/file1.txt", "myapp/file2.txt", "myapp/sub/x.py"]
        s = analyze_structure(names)
        assert s.kind == StructureKind.SINGLE_DIR
        assert s.top_dir == "myapp"
        assert s.top_dir_child_count == 3  # file1, file2, sub

    def test_single_dir_one_child(self) -> None:
        s = analyze_structure(["wrapper/", "wrapper/only.txt"])
        assert s.kind == StructureKind.SINGLE_DIR
        assert s.top_dir_child_count == 1

    def test_multi_files_and_dirs(self) -> None:
        s = analyze_structure(["a.txt", "b.txt", "subdir/c.txt"])
        assert s.kind == StructureKind.MULTI
        assert sorted(s.top_entries) == ["a.txt", "b.txt", "subdir"]

    def test_directory_only_entries_counted(self) -> None:
        s = analyze_structure(["dir/", "dir/sub/"])
        assert s.kind == StructureKind.SINGLE_DIR
        assert s.top_dir == "dir"

    def test_nested_paths_count_only_direct_children(self) -> None:
        names = ["app/", "app/a.txt", "app/sub/b.txt", "app/sub/c.txt"]
        s = analyze_structure(names)
        assert s.kind == StructureKind.SINGLE_DIR
        assert s.top_dir_child_count == 2  # a.txt, sub

    def test_mixed_root_entries_multi(self) -> None:
        s = analyze_structure(["README.md", "src/", "src/main.py", "tests/"])
        assert s.kind == StructureKind.MULTI
        assert "README.md" in s.top_entries
        assert "src" in s.top_entries


class TestStructureKind:
    def test_str_enum_equals_string(self) -> None:
        assert StructureKind.MULTI == "multi"
        assert StructureKind.EMPTY == "empty"
        assert StructureKind.SINGLE_FILE == "single_file"
        assert StructureKind.SINGLE_DIR == "single_dir"

    def test_string_equals_enum(self) -> None:
        assert "multi" == StructureKind.MULTI

    def test_analyze_returns_enum_instance(self) -> None:
        s = analyze_structure(["a.txt", "b.txt"])
        assert s.kind is StructureKind.MULTI
        assert isinstance(s.kind, StructureKind)


class TestArchiveStem:
    def test_zip(self) -> None:
        assert _archive_stem(Path("foo.zip")) == "foo"

    def test_tar_gz(self) -> None:
        assert _archive_stem(Path("foo.tar.gz")) == "foo"

    def test_tar_bz2(self) -> None:
        assert _archive_stem(Path("foo.tar.bz2")) == "foo"

    def test_numbered_split(self) -> None:
        assert _archive_stem(Path("foo.zip.001")) == "foo"

    def test_rar(self) -> None:
        assert _archive_stem(Path("foo.rar")) == "foo"


class TestSmartOutputDir:
    def test_multi_adds_archive_stem(self, tmp_path: Path) -> None:
        s = ArchiveStructure(kind=StructureKind.MULTI)
        assert (
            smart_output_dir(tmp_path / "archive.zip", tmp_path, s)
            == tmp_path / "archive"
        )

    def test_single_dir_uses_base(self, tmp_path: Path) -> None:
        s = ArchiveStructure(
            kind=StructureKind.SINGLE_DIR, top_dir="myapp", top_dir_child_count=5
        )
        assert smart_output_dir(tmp_path / "archive.zip", tmp_path, s) == tmp_path

    def test_single_file_uses_base(self, tmp_path: Path) -> None:
        s = ArchiveStructure(kind=StructureKind.SINGLE_FILE)
        assert smart_output_dir(tmp_path / "archive.zip", tmp_path, s) == tmp_path

    def test_tar_gz_strips_both_suffixes(self, tmp_path: Path) -> None:
        s = ArchiveStructure(kind=StructureKind.MULTI)
        assert (
            smart_output_dir(tmp_path / "myproject.tar.gz", tmp_path, s)
            == tmp_path / "myproject"
        )


class TestSmartRestructure:
    def test_single_child_file_unwrapped(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "only.txt").write_text("content")
        smart_restructure(
            tmp_path,
            ArchiveStructure(
                kind=StructureKind.SINGLE_DIR, top_dir="wrapper", top_dir_child_count=1
            ),
        )
        assert (tmp_path / "only.txt").exists()
        assert not wrapper.exists()

    def test_multi_child_dir_not_unwrapped(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "a.txt").write_text("a")
        (wrapper / "b.txt").write_text("b")
        smart_restructure(
            tmp_path,
            ArchiveStructure(
                kind=StructureKind.SINGLE_DIR, top_dir="wrapper", top_dir_child_count=2
            ),
        )
        assert (wrapper / "a.txt").exists()

    def test_empty_structure_noop(self, tmp_path: Path) -> None:
        smart_restructure(tmp_path, ArchiveStructure(kind=StructureKind.EMPTY))

    def test_missing_wrapper_dir_noop(self, tmp_path: Path) -> None:
        smart_restructure(
            tmp_path,
            ArchiveStructure(
                kind=StructureKind.SINGLE_DIR, top_dir="ghost", top_dir_child_count=1
            ),
        )
        assert list(tmp_path.iterdir()) == []

    def test_extra_hidden_file_prevents_unwrap(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "file.txt").write_text("a")
        (wrapper / ".hidden").write_text("b")
        smart_restructure(
            tmp_path,
            ArchiveStructure(
                kind=StructureKind.SINGLE_DIR, top_dir="wrapper", top_dir_child_count=1
            ),
        )
        assert (wrapper / "file.txt").exists()  # not unwrapped


class TestSmartExtractionEndToEnd:
    def test_multi_root_gets_wrapped(self, tmp_path: Path) -> None:
        from archivetools.operations import extract_archive, list_archive

        z = tmp_path / "files.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("f1.txt", "a")
            zf.writestr("f2.txt", "b")
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
        assert ok
        assert (out / "files" / "f1.txt").exists()

    def test_single_dir_no_double_nest(self, tmp_path: Path) -> None:
        from archivetools.operations import extract_archive, list_archive

        z = tmp_path / "myapp.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("myapp/f1.txt", "x")
            zf.writestr("myapp/f2.txt", "y")
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
        assert ok
        assert (out / "myapp" / "f1.txt").exists()
        assert not (out / "myapp" / "myapp").exists()

    def test_single_child_unwraps(self, tmp_path: Path) -> None:
        from archivetools.operations import extract_archive, list_archive

        z = tmp_path / "wrap.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("wrapper/only.txt", "x")
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
        assert ok
        assert (out / "only.txt").exists()
        assert not (out / "wrapper").exists()
