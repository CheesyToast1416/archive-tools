from __future__ import annotations

from fastapi import APIRouter, Depends

from server.auth import verify_token
from server.models import AppSettingsModel, UIStateModel

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/app", response_model=AppSettingsModel)
def get_app_settings() -> AppSettingsModel:
    from archivetools.config.settings import get_settings

    s = get_settings()
    return AppSettingsModel(
        smart_extraction=s.smart_extraction,
        trash_after_extract=s.trash_after_extract,
        default_output_dir=s.default_output_dir,
        trash_after_create=s.trash_after_create,
        trash_after_batch=s.trash_after_batch,
        default_password_encoding=s.default_password_encoding,
        default_filename_encoding=s.default_filename_encoding,
        notifications_enabled=s.notifications_enabled,
    )


@router.put("/app")
def save_app_settings(body: AppSettingsModel) -> dict:
    from archivetools.config.settings import get_settings

    s = get_settings()
    s.smart_extraction = body.smart_extraction
    s.trash_after_extract = body.trash_after_extract
    s.default_output_dir = body.default_output_dir
    s.trash_after_create = body.trash_after_create
    s.trash_after_batch = body.trash_after_batch
    s.default_password_encoding = body.default_password_encoding
    s.default_filename_encoding = body.default_filename_encoding
    s.notifications_enabled = body.notifications_enabled
    s.save()
    return {"ok": True}


@router.get("/ui", response_model=UIStateModel)
def get_ui_state() -> UIStateModel:
    from archivetools.gui.ui_state import get_ui_state

    u = get_ui_state()
    return UIStateModel(
        theme=u.theme,
        active_nav=u.active_nav,
        recent_archives=list(u.recent_archives),
        last_archive_dir=u.last_archive_dir,
    )


@router.put("/ui")
def save_ui_state(body: UIStateModel) -> dict:
    from archivetools.gui.ui_state import get_ui_state

    u = get_ui_state()
    u.theme = body.theme
    u.active_nav = body.active_nav
    u.recent_archives = body.recent_archives[:15]
    u.last_archive_dir = body.last_archive_dir
    u.save()
    return {"ok": True}
