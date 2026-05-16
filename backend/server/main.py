from __future__ import annotations

import json
import os
import shutil
import socket
import sys
from contextlib import asynccontextmanager

# When run as a script (python server/main.py), insert the project root so
# that both `server.*` and `archivetools.*` are importable.  Has no effect
# when invoked as a module (python -m server.main) or via PyInstaller.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

from server._token import TOKEN

# Set in __main__ before uvicorn.run() so the lifespan can reference it.
_port: int = 0


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@asynccontextmanager
async def _lifespan(app):
    # uvicorn has already bound the socket before running lifespan startup,
    # so printing here guarantees the server is accepting connections when
    # Tauri reads the handshake line.
    print(json.dumps({"port": _port, "token": TOKEN}), flush=True)

    yield

    # Clean up lingering preview temp dirs on graceful shutdown.
    from server.routes.preview import _PREVIEW_DIRS

    for tmpdir in list(_PREVIEW_DIRS.values()):
        shutil.rmtree(tmpdir, ignore_errors=True)
    _PREVIEW_DIRS.clear()


def create_app():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from server.routes import archives, passwords, preview
    from server.routes import settings as settings_routes

    app = FastAPI(
        title="ArchiveTools Server",
        docs_url=None,
        redoc_url=None,
        lifespan=_lifespan,
    )

    # Allow the Tauri WebView to call this server regardless of origin.
    # Dev mode:        http://localhost:1420  (Vite dev server)
    # Production:      tauri://localhost      (Tauri asset protocol, all platforms)
    # macOS/Windows alt: https://tauri.localhost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(archives.router, prefix="/archives")
    app.include_router(preview.router, prefix="/preview")
    app.include_router(passwords.router, prefix="/passwords")
    app.include_router(settings_routes.router, prefix="/settings")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    return app


if __name__ == "__main__":
    _port = _find_free_port()
    uvicorn.run(create_app(), host="127.0.0.1", port=_port, log_level="warning")
