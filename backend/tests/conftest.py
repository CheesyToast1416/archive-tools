"""Shared fixtures for ArchiveTools backend tests.

Archive-creation helpers live here so individual test files don't repeat them.
The ``client`` and ``auth`` fixtures provide a ready-to-use FastAPI TestClient.
"""

from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

import pytest
import pyzipper

from server._token import TOKEN
from server.main import create_app

# ── Source material ────────────────────────────────────────────────────────────


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """A temp directory with two sample files."""
    d = tmp_path / "src"
    d.mkdir()
    (d / "hello.txt").write_text("Hello, world!")
    (d / "data.csv").write_text("a,b,c\n1,2,3\n")
    return d


# ── Archive fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def simple_zip(tmp_path: Path) -> Path:
    """ZIP with hello.txt and subdir/nested.txt at root."""
    p = tmp_path / "archive.zip"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", "Hello, world!")
        zf.writestr("subdir/nested.txt", "nested content")
    return p


@pytest.fixture
def nested_zip(tmp_path: Path) -> Path:
    """ZIP with all entries under a single 'pkg/' directory (multi-child)."""
    p = tmp_path / "nested.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("pkg/", "")
        zf.writestr("pkg/hello.txt", "hello")
        zf.writestr("pkg/data.csv", "a,b")
        zf.writestr("pkg/sub/deep.txt", "deep")
    return p


@pytest.fixture
def single_child_zip(tmp_path: Path) -> Path:
    """ZIP with a single file inside one wrapper dir (should be unwrapped)."""
    p = tmp_path / "single.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("wrapper/", "")
        zf.writestr("wrapper/only.txt", "content")
    return p


@pytest.fixture
def encrypted_zip(tmp_path: Path) -> Path:
    """AES-256 encrypted ZIP archive."""
    p = tmp_path / "secret.zip"
    with pyzipper.AESZipFile(p, "w", encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(b"correcthorsebattery")
        zf.writestr("secret.txt", "top secret content")
    return p


@pytest.fixture
def simple_tar(tmp_path: Path) -> Path:
    """Plain TAR with hello.txt and data.csv."""
    p = tmp_path / "archive.tar"
    with tarfile.open(p, "w") as tf:
        import io

        for name, content in [("hello.txt", "Hello, world!"), ("data.csv", "a,b,c")]:
            data = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return p


@pytest.fixture
def simple_tar_gz(tmp_path: Path) -> Path:
    """Gzip-compressed TAR."""
    p = tmp_path / "archive.tar.gz"
    with tarfile.open(p, "w:gz") as tf:
        import io

        data = b"Hello, gzip!"
        info = tarfile.TarInfo(name="hello.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    return p


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """An empty output directory."""
    d = tmp_path / "out"
    d.mkdir()
    return d


# ── FastAPI test client ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def _app():
    """Single app instance for the entire test session."""
    return create_app()


@pytest.fixture
def client(_app):
    """Function-scoped TestClient — each test gets a clean transport."""
    from fastapi.testclient import TestClient

    with TestClient(_app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth() -> dict[str, str]:
    """Bearer-token auth headers."""
    return {"Authorization": f"Bearer {TOKEN}"}


# ── SSE helper ─────────────────────────────────────────────────────────────────


def parse_sse(text: str) -> list[dict]:
    """Parse an SSE response body into [{event, data}, ...] list."""
    events: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        if line.startswith("event: "):
            current["event"] = line[7:].strip()
        elif line.startswith("data: "):
            try:
                current["data"] = json.loads(line[6:])
            except json.JSONDecodeError:
                current["data"] = line[6:]
        elif line == "" and current:
            events.append(current.copy())
            current = {}
    if current:
        events.append(current)
    return events
