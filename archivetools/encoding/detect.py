from __future__ import annotations

import zipfile
from pathlib import Path


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
                if info.flag_bits & 0x800:   # already UTF-8 — skip
                    continue
                try:
                    raw_samples.append(info.filename.encode("cp437"))
                except UnicodeEncodeError:
                    continue
        return detect_filename_encoding(raw_samples)
    except Exception:  # noqa: BLE001
        return None, 0.0
