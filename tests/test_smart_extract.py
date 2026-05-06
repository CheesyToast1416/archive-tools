from __future__ import annotations

import zipfile
from pathlib import Path

from archivetools.operations.extract import (
    ArchiveStructure,
    _archive_stem,
    analyze_structure,
    smart_output_dir,
    smart_restructure,
)


class TestAnalyzeStructure:
    def test_empty(self) -> None:
        assert analyze_structure([]).kind == "empty"
        assert analyze_structure(["", "/"]).kind == "empty"

    def test_single_file(self) -> None:
        s = analyze_structure(["readme.txt"])
        assert s.kind == "single_file"
        assert s.top_entries == ["readme.txt"]

    def test_single_dir_multi_children(self) -> None:
        names = ["myapp/", "myapp/file1.txt", "myapp/file2.txt", "myapp/sub/x.py"]
        s = analyze_structure(names)
        assert s.kind == "single_dir"
        assert s.top_dir == "myapp"
        assert s.top_dir_child_count == 3  # file1, file2, sub

    def test_single_dir_one_child(self) -> None:
        names = ["wrapper/", "wrapper/only.txt"]
        s = analyze_structure(names)
        assert s.kind == "single_dir"
        assert s.top_dir_child_count == 1

    def test_multi(self) -> None:
        names = ["a.txt", "b.txt", "subdir/c.txt"]
        s = analyze_structure(names)
        assert s.kind == "multi"
        assert sorted(s.top_entries) == ["a.txt", "b.txt", "subdir"]


class TestSmartOutputDir:
    def test_multi_adds_stem(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive.zip"
        s = ArchiveStructure(kind="multi")
        assert smart_output_dir(archive, tmp_path, s) == tmp_path / "archive"

    def test_single_dir_uses_base(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive.zip"
        s = ArchiveStructure(kind="single_dir", top_dir="myapp", top_dir_child_count=5)
        assert smart_output_dir(archive, tmp_path, s) == tmp_path

    def test_single_file_uses_base(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive.zip"
        s = ArchiveStructure(kind="single_file")
        assert smart_output_dir(archive, tmp_path, s) == tmp_path

    def test_tar_gz_stem(self, tmp_path: Path) -> None:
        archive = tmp_path / "myproject.tar.gz"
        s = ArchiveStructure(kind="multi")
        assert smart_output_dir(archive, tmp_path, s) == tmp_path / "myproject"


class TestArchiveStem:
    def test_zip(self) -> None:
        assert _archive_stem(Path("foo.zip")) == "foo"

    def test_tar_gz(self) -> None:
        assert _archive_stem(Path("foo.tar.gz")) == "foo"

    def test_split(self) -> None:
        assert _archive_stem(Path("foo.zip.001")) == "foo"

    def test_rar(self) -> None:
        assert _archive_stem(Path("foo.rar")) == "foo"


class TestSmartRestructure:
    def test_single_child_file_unwrapped(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "only.txt").write_text("hello")

        s = ArchiveStructure(
            kind="single_dir", top_dir="wrapper", top_dir_child_count=1
        )
        smart_restructure(tmp_path, s)

        assert (tmp_path / "only.txt").exists()
        assert not wrapper.exists()

    def test_single_child_dir_unwrapped(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        sub = wrapper / "subdir"
        sub.mkdir(parents=True)
        (sub / "file.txt").write_text("x")

        s = ArchiveStructure(
            kind="single_dir", top_dir="wrapper", top_dir_child_count=1
        )
        smart_restructure(tmp_path, s)

        assert (tmp_path / "subdir" / "file.txt").exists()
        assert not wrapper.exists()

    def test_multi_children_not_touched(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "a.txt").write_text("a")
        (wrapper / "b.txt").write_text("b")

        s = ArchiveStructure(
            kind="single_dir", top_dir="wrapper", top_dir_child_count=2
        )
        smart_restructure(tmp_path, s)

        # Nothing should be moved
        assert (wrapper / "a.txt").exists()
        assert (wrapper / "b.txt").exists()

    def test_collision_preserved(self, tmp_path: Path) -> None:
        wrapper = tmp_path / "wrapper"
        wrapper.mkdir()
        (wrapper / "clash.txt").write_text("from archive")
        (tmp_path / "clash.txt").write_text("pre-existing")  # collision

        s = ArchiveStructure(
            kind="single_dir", top_dir="wrapper", top_dir_child_count=1
        )
        smart_restructure(tmp_path, s)

        # Should NOT overwrite; wrapper stays
        assert (tmp_path / "clash.txt").read_text() == "pre-existing"


class TestEndToEnd:
    def _make_zip(self, path: Path, entries: dict[str, str]) -> Path:
        with zipfile.ZipFile(path, "w") as zf:
            for name, content in entries.items():
                zf.writestr(name, content)
        return path

    def test_multi_archive_gets_wrapper(self, tmp_path: Path) -> None:
        from archivetools.operations.extract import extract_cjk

        z = self._make_zip(
            tmp_path / "archive.zip",
            {"a.txt": "aaa", "b.txt": "bbb"},
        )
        dest = tmp_path / "out"
        dest.mkdir()

        ok, _ = extract_cjk(
            z,
            "",
            str(dest),
            filename_encoding=None,
            password_encoding=None,
            names=["a.txt", "b.txt"],
            smart=True,
        )
        assert ok
        # Files should be inside out/archive/ not scattered in out/
        assert (dest / "archive" / "a.txt").exists()
        assert (dest / "archive" / "b.txt").exists()

    def test_single_dir_archive_no_double_wrap(self, tmp_path: Path) -> None:
        from archivetools.operations.extract import extract_cjk

        z = self._make_zip(
            tmp_path / "myapp.zip",
            {"myapp/file1.txt": "x", "myapp/file2.txt": "y"},
        )
        dest = tmp_path / "out"
        dest.mkdir()

        ok, _ = extract_cjk(
            z,
            "",
            str(dest),
            filename_encoding=None,
            password_encoding=None,
            names=["myapp/file1.txt", "myapp/file2.txt"],
            smart=True,
        )
        assert ok
        # Should be out/myapp/file1.txt — not out/myapp/myapp/file1.txt
        assert (dest / "myapp" / "file1.txt").exists()

    def test_single_wrapper_child_unwrapped(self, tmp_path: Path) -> None:
        from archivetools.operations.extract import extract_cjk

        z = self._make_zip(
            tmp_path / "release.zip",
            {"wrapper/subproject/file.txt": "hello"},
        )
        dest = tmp_path / "out"
        dest.mkdir()

        ok, _ = extract_cjk(
            z,
            "",
            str(dest),
            filename_encoding=None,
            password_encoding=None,
            names=["wrapper/", "wrapper/subproject/", "wrapper/subproject/file.txt"],
            smart=True,
        )
        assert ok
        # wrapper/ had one child (subproject) → unwrapped
        assert (dest / "subproject" / "file.txt").exists()
        assert not (dest / "wrapper").exists()
