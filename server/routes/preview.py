from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from server.auth import verify_token
from server.models import PreviewRequest, PreviewResponse

router = APIRouter(dependencies=[Depends(verify_token)])

# temp_id → absolute path of the temp directory
_PREVIEW_DIRS: dict[str, str] = {}
# temp_id → creation timestamp (monotonic)
_PREVIEW_TIMES: dict[str, float] = {}

_MAX_AGE_SECONDS = 1800.0  # 30 minutes


def _cleanup_stale() -> None:
    now = time.monotonic()
    stale = [
        tid for tid, ts in list(_PREVIEW_TIMES.items()) if now - ts > _MAX_AGE_SECONDS
    ]
    for tid in stale:
        tmpdir = _PREVIEW_DIRS.pop(tid, None)
        _PREVIEW_TIMES.pop(tid, None)
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


@router.post("/", response_model=PreviewResponse)
def extract_preview(req: PreviewRequest) -> PreviewResponse:
    from archivetools.operations import extract_archive

    _cleanup_stale()

    temp_id = str(uuid.uuid4())
    tmpdir = tempfile.mkdtemp(prefix="atpreview_")
    try:
        ok, _ = extract_archive(
            req.archive_path,
            req.password,
            tmpdir,
            filename_encoding=req.filename_encoding,
            password_encoding=req.password_encoding,
            smart=False,
        )
        if not ok:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(
                status_code=422, detail="Extraction failed (wrong password?)"
            )

        file_path = _locate_entry(tmpdir, req.entry_name)
        if file_path is None:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(
                status_code=404, detail="Entry not found after extraction"
            )

        _PREVIEW_DIRS[temp_id] = tmpdir
        _PREVIEW_TIMES[temp_id] = time.monotonic()
        return PreviewResponse(temp_id=temp_id, file_path=file_path)
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/serve")
def serve_preview_file(path: str) -> FileResponse:
    """Serve an extracted preview file by absolute path.

    Auth is handled by the router-level verify_token dependency, which accepts
    the token via ?token= query param so <video>/<audio> src attributes work.
    """
    p = Path(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(p))


@router.delete("/{temp_id}")
def cleanup_preview(temp_id: str) -> dict:
    tmpdir = _PREVIEW_DIRS.pop(temp_id, None)
    _PREVIEW_TIMES.pop(temp_id, None)
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return {"ok": True}


def _locate_entry(tmpdir: str, entry_name: str) -> str | None:
    """Mirror of PreviewWorker._locate_entry from gui/workers.py."""
    direct = Path(tmpdir) / entry_name
    if direct.is_file():
        return str(direct)

    stripped = Path(tmpdir) / entry_name.lstrip("./")
    if stripped.is_file():
        return str(stripped)

    target = Path(entry_name).name
    for root, _dirs, files in os.walk(tmpdir):
        for fname in files:
            if fname == target:
                return os.path.join(root, fname)

    for root, _dirs, files in os.walk(tmpdir):
        if files:
            return os.path.join(root, files[0])

    return None
