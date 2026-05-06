from __future__ import annotations

import zipfile
from pathlib import Path

# RAR4 unicode flag — filenames with this flag are already stored as UTF-16
_RAR4_FLAG_UNICODE = 0x200


def detect_filename_encoding(
    raw_bytes_list: list[bytes],
) -> tuple[str | None, float]:
    """
    Run charset-normalizer on a batch of raw filename bytes.

    Returns ``(encoding_name, confidence)`` where *confidence* is 0.0–1.0.
    Returns ``(None, 0.0)`` when the sample is too small or ambiguous.
    """
    if not raw_bytes_list:
        return None, 0.0

    try:
        from charset_normalizer import from_bytes  # type: ignore[import]
    except ImportError:
        return None, 0.0

    combined = b"\n".join(raw_bytes_list)
    best = from_bytes(combined).best()
    if best is None or not best.encoding:
        return None, 0.0

    # charset_normalizer's `chaos` is a "messiness" score (0 = clean, 1 = chaos).
    confidence = max(0.0, 1.0 - best.chaos)
    return best.encoding, round(confidence, 2)


def detect_zip_filename_encoding(
    archive_path: Path,
) -> tuple[str | None, float]:
    """
    Collect raw (CP437-decoded-then-re-encoded) filename bytes from a ZIP
    and run detection.  Skips entries that have the UTF-8 flag set.
    """
    try:
        raw_samples: list[bytes] = []
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                if info.flag_bits & 0x800:  # already UTF-8 — skip
                    continue
                try:
                    raw_samples.append(info.filename.encode("cp437"))
                except UnicodeEncodeError:
                    continue
        return detect_filename_encoding(raw_samples)
    except Exception:  # noqa: BLE001
        return None, 0.0


def detect_rar_filename_encoding(
    archive_path: Path,
) -> tuple[str | None, float]:
    """
    Detect the filename encoding used in a RAR archive.

    For RAR5 (all UTF-8) and ASCII-only archives, returns ``(None, 0.0)``.
    For RAR4 archives with non-ASCII filenames, re-encodes the decoded
    filename strings as Latin-1 to recover the original bytes, then runs
    charset-normalizer to identify the encoding (e.g. GBK, Shift-JIS).
    """
    try:
        import rarfile  # type: ignore[import]
    except ImportError:
        return None, 0.0
    try:
        raw_samples: list[bytes] = []
        with rarfile.RarFile(str(archive_path)) as rf:
            for info in rf.infolist():
                name: str = info.filename
                # Pure ASCII filenames carry no encoding information
                try:
                    name.encode("ascii")
                    continue
                except UnicodeEncodeError:
                    pass
                # RAR5 filenames are UTF-8 and will decode to non-Latin-1 code
                # points for CJK; we can't recover the original bytes via Latin-1
                # re-encoding in that case, so skip them.
                try:
                    raw_samples.append(name.encode("latin-1"))
                except UnicodeEncodeError:
                    continue
        return detect_filename_encoding(raw_samples)
    except Exception:  # noqa: BLE001
        return None, 0.0
