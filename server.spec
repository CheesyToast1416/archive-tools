# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the ArchiveTools sidecar server binary.
# Run from the repository root: pyinstaller server.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules

a_uvicorn   = collect_all("uvicorn")
a_fastapi   = collect_all("fastapi")
a_starlette = collect_all("starlette")
a_sse       = collect_all("sse_starlette")

a = Analysis(
    ["server/main.py"],
    pathex=["."],
    binaries=a_uvicorn[1] + a_fastapi[1] + a_starlette[1],
    datas=a_uvicorn[0] + a_fastapi[0] + a_starlette[0] + a_sse[0],
    hiddenimports=(
        a_uvicorn[2]
        + a_fastapi[2]
        + a_starlette[2]
        + a_sse[2]
        + collect_submodules("server")
        + collect_submodules("archivetools")
        + collect_submodules("keyring")
        + [
            "h11",
            "httptools",
            "anyio",
            "anyio._backends._asyncio",
            "anyio._backends._trio",
            "click",
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy GUI / scientific packages that the server never imports.
    excludes=[
        "PySide6", "PySide2", "PyQt5", "PyQt6",
        "tkinter", "wx",
        "matplotlib", "numpy", "pandas", "scipy",
        "PIL", "cv2",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Single-file executable — binaries and datas are embedded.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="archivetools-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX can corrupt some binaries on macOS/Windows
    console=True,       # MUST be True: server prints handshake JSON to stdout
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
