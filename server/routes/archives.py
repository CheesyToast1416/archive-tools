from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from server.auth import verify_token
from server.models import (
    BatchRequest,
    ConvertRequest,
    CreateRequest,
    DetectEncodingResponse,
    ExtractRequest,
    InfoResponse,
    ListRequest,
    ListResponse,
    TestRequest,
    TestResponse,
    UpdateRequest,
)

router = APIRouter(dependencies=[Depends(verify_token)])


# ── Synchronous (non-streaming) routes ───────────────────────────────────────


@router.post("/list", response_model=ListResponse)
def list_archive_route(req: ListRequest) -> ListResponse:
    try:
        from archivetools.operations import list_archive

        ok, enc, names = list_archive(
            req.archive_path,
            req.password,
            req.filename_encoding,
            req.password_encoding,
        )
        return ListResponse(ok=ok, encoding=enc, names=names)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/info", response_model=InfoResponse)
def get_info_route(req: ListRequest) -> InfoResponse:
    try:
        from archivetools.operations import get_archive_info

        info = get_archive_info(req.archive_path)
        return InfoResponse(
            format_name=info.format_name,
            file_count=info.file_count,
            compressed_size=info.compressed_size,
            uncompressed_size=info.uncompressed_size,
            is_encrypted=info.is_encrypted,
            comment=info.comment or "",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/detect-encoding", response_model=DetectEncodingResponse)
def detect_encoding_route(req: ListRequest) -> DetectEncodingResponse:
    try:
        from archivetools.operations import detect_archive_encoding

        enc, conf = detect_archive_encoding(req.archive_path)
        return DetectEncodingResponse(encoding=enc, confidence=conf)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/test", response_model=TestResponse)
def test_archive_route(req: TestRequest) -> TestResponse:
    try:
        from archivetools.operations import test_archive

        ok, failed = test_archive(
            req.archive_path,
            req.password,
            filename_encoding=req.filename_encoding,
            password_encoding=req.password_encoding,
        )
        return TestResponse(ok=ok, failed=failed)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/create")
def create_archive_route(req: CreateRequest) -> dict:
    try:
        from archivetools.operations import create_archive

        ok = create_archive(
            req.output_path,
            req.files,
            format=req.format,
            password=req.password,
            compression_level=req.compression_level,
            filename_encoding=req.filename_encoding,
        )
        return {"ok": ok}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/convert")
def convert_archive_route(req: ConvertRequest) -> dict:
    try:
        from archivetools.operations import convert_archive

        ok = convert_archive(
            req.input_path,
            req.output_path,
            req.output_format,
            password=req.password,
            output_password=req.output_password,
            filename_encoding=req.filename_encoding,
            password_encoding=req.password_encoding,
        )
        return {"ok": ok}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/update")
def update_archive_route(req: UpdateRequest) -> dict:
    try:
        from archivetools.operations import update_archive

        # update_archive declares list[str | Path]; list[str] is valid at runtime.
        ok = update_archive(
            req.archive_path,
            files_to_add=req.files_to_add,  # type: ignore[arg-type]
            paths_to_remove=req.paths_to_remove,  # type: ignore[arg-type]
        )
        return {"ok": ok}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── SSE helpers ───────────────────────────────────────────────────────────────


def _sse(event: str, data: object) -> dict:
    return {"event": event, "data": json.dumps(data)}


class _SSELogHandler(logging.Handler):
    """Forwards log records to an asyncio Queue as SSE log events."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._q = queue
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._loop.call_soon_threadsafe(
            self._q.put_nowait, _sse("log", {"message": msg})
        )


def _attach_log_handler(handler: logging.Handler) -> None:
    for name in ("archivetools.formats", "archivetools.operations"):
        logging.getLogger(name).addHandler(handler)


def _detach_log_handler(handler: logging.Handler) -> None:
    for name in ("archivetools.formats", "archivetools.operations"):
        logging.getLogger(name).removeHandler(handler)


# ── Extract (SSE) ─────────────────────────────────────────────────────────────


@router.post("/extract")
async def extract_route(req: ExtractRequest) -> EventSourceResponse:
    async def event_generator() -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        log_handler = _SSELogHandler(q, loop)

        def progress_cb(current: int, total: int, filename: str) -> None:
            loop.call_soon_threadsafe(
                q.put_nowait,
                _sse(
                    "progress",
                    {"current": current, "total": total, "filename": filename},
                ),
            )

        def bytes_cb(done: int, total: int) -> None:
            loop.call_soon_threadsafe(
                q.put_nowait, _sse("bytes_progress", {"done": done, "total": total})
            )

        def run() -> None:
            _attach_log_handler(log_handler)
            try:
                from archivetools.operations import extract_archive

                ok, enc = extract_archive(
                    req.archive_path,
                    req.password,
                    req.output_dir,
                    filename_encoding=req.filename_encoding,
                    password_encoding=req.password_encoding,
                    progress=progress_cb,
                    bytes_progress=bytes_cb,
                    names=req.names,
                    smart=req.smart,
                )
                event = "complete" if ok else "error"
                loop.call_soon_threadsafe(
                    q.put_nowait, _sse(event, {"ok": ok, "encoding": enc})
                )
            except Exception as exc:
                loop.call_soon_threadsafe(
                    q.put_nowait, _sse("error", {"message": str(exc)})
                )
            finally:
                _detach_log_handler(log_handler)
                loop.call_soon_threadsafe(q.put_nowait, None)

        threading.Thread(target=run, daemon=True).start()
        while True:
            item = await q.get()
            if item is None:
                break
            yield item

    return EventSourceResponse(event_generator())


# ── Batch extract (SSE) ───────────────────────────────────────────────────────


@router.post("/batch")
async def batch_route(req: BatchRequest) -> EventSourceResponse:
    async def event_generator() -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        log_handler = _SSELogHandler(q, loop)

        def file_progress_cb(current: int, total: int, filename: str) -> None:
            loop.call_soon_threadsafe(
                q.put_nowait,
                _sse(
                    "file_progress",
                    {"current": current, "total": total, "filename": filename},
                ),
            )

        def bytes_cb(done: int, total: int) -> None:
            loop.call_soon_threadsafe(
                q.put_nowait, _sse("bytes_progress", {"done": done, "total": total})
            )

        def run() -> None:
            _attach_log_handler(log_handler)
            ok_count = 0
            fail_count = 0
            try:
                from archivetools.operations import extract_archive, list_archive

                for idx, archive_path in enumerate(req.archives):
                    loop.call_soon_threadsafe(
                        q.put_nowait, _sse("archive_started", {"index": idx})
                    )
                    try:
                        # Pre-list to enable smart extraction
                        _, _, names = list_archive(
                            archive_path,
                            req.password,
                            req.filename_encoding,
                            req.password_encoding,
                        )
                        ok, enc = extract_archive(
                            archive_path,
                            req.password,
                            req.output_dir,
                            filename_encoding=req.filename_encoding,
                            password_encoding=req.password_encoding,
                            progress=file_progress_cb,
                            bytes_progress=bytes_cb,
                            names=names,
                            smart=True,
                        )
                        detail = f"encoding: {enc}" if enc else ""
                        if ok:
                            ok_count += 1
                        else:
                            fail_count += 1
                        loop.call_soon_threadsafe(
                            q.put_nowait,
                            _sse(
                                "archive_done",
                                {"index": idx, "ok": ok, "detail": detail},
                            ),
                        )
                    except Exception as exc:
                        fail_count += 1
                        loop.call_soon_threadsafe(
                            q.put_nowait,
                            _sse(
                                "archive_done",
                                {"index": idx, "ok": False, "detail": str(exc)},
                            ),
                        )

                loop.call_soon_threadsafe(
                    q.put_nowait,
                    _sse("complete", {"ok_count": ok_count, "fail_count": fail_count}),
                )
            except Exception as exc:
                loop.call_soon_threadsafe(
                    q.put_nowait, _sse("error", {"message": str(exc)})
                )
            finally:
                _detach_log_handler(log_handler)
                loop.call_soon_threadsafe(q.put_nowait, None)

        threading.Thread(target=run, daemon=True).start()
        while True:
            item = await q.get()
            if item is None:
                break
            yield item

    return EventSourceResponse(event_generator())
