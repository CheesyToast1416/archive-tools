from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def move_to_trash(path: str | Path) -> bool:
    """
    Move *path* to the system trash / recycle bin.

    Returns ``True`` on success.  On failure the error is logged as a warning
    and ``False`` is returned — the caller should inform the user but must not
    treat this as a fatal error.
    """
    try:
        from send2trash import send2trash  # type: ignore[import]

        send2trash(str(path))
        log.info("Moved to trash: %s", path)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not move to trash: %s — %s", path, exc)
        return False


def trash_paths(paths: list[str | Path]) -> tuple[int, list[str]]:
    """
    Attempt to trash each path in *paths*.

    Returns ``(success_count, failed_paths)``.
    """
    failed: list[str] = []
    ok = 0
    for p in paths:
        if move_to_trash(p):
            ok += 1
        else:
            failed.append(str(p))
    return ok, failed
