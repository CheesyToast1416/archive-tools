from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_APP_NAME = "ArchiveTools"


def notify(title: str, body: str) -> None:
    """
    Show a desktop notification using plyer.

    Silently no-ops if:
    - notifications are disabled in settings
    - plyer is unavailable
    - the platform lacks a notification backend
    """
    from archivetools.config.settings import get_settings

    if not get_settings().notifications_enabled:
        return

    try:
        from plyer import notification  # type: ignore[import]

        notification.notify(
            title=title,
            message=body,
            app_name=_APP_NAME,
            timeout=4,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("Desktop notification unavailable: %s", exc)
