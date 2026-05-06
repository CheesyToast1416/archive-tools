from __future__ import annotations

import logging
import os
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from archivetools.formats import detect_handler

log = logging.getLogger(__name__)


# ── Archive structure analysis ────────────────────────────────────────────────


@dataclass
class ArchiveStructure:
    """Summary of what sits at the root level of an archive."""

    # "empty" | "single_file" | "single_dir" | "multi"
    kind: str
    # All distinct top-level entry names (without trailing slash)
    top_entries: list[str] = field(default_factory=list)
    # For kind == "single_dir": name of that dir
    top_dir: str | None = None
    # For kind == "single_dir": number of DIRECT children of that dir
    top_dir_child_count: int = 0


def analyze_structure(names: list[str]) -> ArchiveStructure:
    """
    Inspect an archive's entry list and classify its root layout.

    Returns an :class:`ArchiveStructure` describing what sits at the top level
    so that extraction can choose the right output directory and, if needed,
    collapse pointless wrapper directories afterwards.
    """
    tops: dict[str, set[str]] = {}
    for raw in names:
        name = raw.rstrip("/")
        if not name:
            continue
        parts = name.split("/")
        top = parts[0]
        if top not in tops:
            tops[top] = set()
        if len(parts) >= 2 and parts[1]:
            tops[top].add(parts[1])

    entries = sorted(tops.keys())

    if not entries:
        return ArchiveStructure(kind="empty")

    if len(entries) == 1:
        top = entries[0]
        children = tops[top]
        if not children:
            return ArchiveStructure(kind="single_file", top_entries=entries)
        return ArchiveStructure(
            kind="single_dir",
            top_entries=entries,
            top_dir=top,
            top_dir_child_count=len(children),
        )

    return ArchiveStructure(kind="multi", top_entries=entries)


def _archive_stem(archive_path: Path) -> str:
    """Return the archive's name without extension(s)."""
    name = archive_path.name
    name = re.sub(r"\.\d+$", "", name)  # strip split suffixes (.001)
    for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    p = Path(name)
    if p.suffix.lower() in (".zip", ".rar", ".7z", ".tar", ".z"):
        return p.stem
    return name


def smart_output_dir(
    archive_path: Path,
    base_output: Path,
    structure: ArchiveStructure,
) -> Path:
    """
    Choose the directory to extract INTO, adjusted for archive layout.

    Rules
    -----
    * **multi** (no top-level directory): extract into ``base_output/<stem>/``
      so the destination isn't polluted by loose files.
    * **single_dir** or **single_file**: extract into ``base_output`` and let
      the archive's own directory (if any) act as the natural wrapper.
    * **empty**: no-op, returns ``base_output``.
    """
    if structure.kind == "multi":
        return base_output / _archive_stem(archive_path)
    return base_output


def smart_restructure(output_dir: Path, structure: ArchiveStructure) -> None:
    """
    Post-extraction: collapse a trivially thin wrapper directory.

    Triggered when the archive had **exactly one top-level directory** that
    itself contained **exactly one direct child** (file or sub-directory).
    In that case the wrapper adds no useful nesting, so it is stripped:

        output_dir/wrapper/only_child/  →  output_dir/only_child/
        output_dir/wrapper/only_file    →  output_dir/only_file
    """
    if structure.kind != "single_dir" or structure.top_dir_child_count != 1:
        return
    if structure.top_dir is None:
        return

    wrapper = output_dir / structure.top_dir
    if not wrapper.is_dir():
        return

    real_children = [p for p in wrapper.iterdir()]
    if len(real_children) != 1:
        # Post-extraction child count differs (e.g. hidden files) — leave alone.
        return

    only_child = real_children[0]
    target = output_dir / only_child.name

    if target.exists():
        # Name collision — keep wrapper to avoid data loss.
        log.debug("Smart-restructure skipped: %s already exists", target)
        return

    only_child.rename(target)
    try:
        wrapper.rmdir()
    except OSError:
        # rmdir fails if wrapper is non-empty (shouldn't happen, but be safe)
        shutil.move(str(target), str(wrapper / only_child.name))
        log.debug("Smart-restructure rollback: could not remove %s", wrapper)
        return

    log.info(
        "Smart extraction: collapsed wrapper '%s' → '%s'", wrapper.name, target.name
    )


# ── Default output directory (non-smart fallback) ────────────────────────────


def _default_output_dir(archive_path: Path) -> Path:
    """Derive a clean output directory name from the archive path."""
    stem = _archive_stem(archive_path)
    return archive_path.parent / (stem or archive_path.stem)


# ── Public extraction entry point ─────────────────────────────────────────────


def extract_cjk(
    archive_path: str | os.PathLike,
    password: str,
    output_dir: str | os.PathLike | None = None,
    *,
    filename_encoding: str | None = None,
    password_encoding: str | None = None,
    verbose: bool = True,
    progress: Callable[[int, int, str], None] | None = None,
    bytes_progress: Callable[[int, int], None] | None = None,
    names: list[str] | None = None,
    smart: bool = True,
) -> tuple[bool, str | None]:
    """
    Extract *archive_path* with CJK password/filename encoding support.

    Parameters
    ----------
    names:
        Pre-fetched file list (from a prior :func:`list_cjk` call).  When
        provided together with ``smart=True``, the destination directory is
        adjusted automatically and a pointless wrapper directory may be
        collapsed after extraction.
    smart:
        Enable smart-extraction heuristics (default ``True``).  Requires
        *names* to be supplied; silently falls back to the plain behaviour
        if *names* is ``None``.
    """
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    structure: ArchiveStructure | None = None

    if smart and names is not None:
        structure = analyze_structure(names)
        # Base dir: either the user-specified dir or the archive's parent
        base = Path(output_dir) if output_dir else archive_path.parent
        dest = smart_output_dir(archive_path, base, structure)
    else:
        dest = Path(output_dir) if output_dir else _default_output_dir(archive_path)

    dest.mkdir(parents=True, exist_ok=True)

    handler, canonical = detect_handler(archive_path)
    ok, enc = handler.extract(
        canonical,
        password,
        dest,
        filename_encoding=filename_encoding,
        password_encoding=password_encoding,
        verbose=verbose,
        progress=progress,
        bytes_progress=bytes_progress,
    )

    if ok and structure is not None:
        smart_restructure(dest, structure)
        if verbose:
            log.info("Output: %s", dest)

    return ok, enc
