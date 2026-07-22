from __future__ import annotations

import asyncio
import stat
from pathlib import Path

import httpx
import pytest

from src.config import Settings, settings
from src.main import app
from src.tools import sandbox_fs


@pytest.fixture
def sandbox_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure an isolated sandbox root for one test."""
    root = tmp_path / "sandboxes"
    monkeypatch.setattr(settings, "SANDBOX_ROOT", root)
    return root


def post_to_app(path: str) -> httpx.Response:
    """POST through the ASGI stack without opening a network socket."""

    async def post() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(path)

    return asyncio.run(post())


def test_read_write_list_and_api_burn(sandbox_root: Path) -> None:
    session_id = "normal-session"
    sandbox_fs.write_text(session_id, "nested/example.txt", "sandboxed")

    assert sandbox_fs.read_text(session_id, "nested/example.txt") == "sandboxed"
    assert sandbox_fs.list_dir(session_id, "nested") == ["example.txt"]
    assert stat.S_IMODE((sandbox_root / session_id).stat().st_mode) == 0o700
    assert stat.S_IMODE((sandbox_root / session_id / "nested").stat().st_mode) == 0o700
    assert stat.S_IMODE((sandbox_root / session_id / "nested/example.txt").stat().st_mode) == 0o600

    response = post_to_app(f"/api/session/burn/{session_id}")

    assert response.status_code == 204
    assert not (sandbox_root / session_id).exists()


@pytest.mark.parametrize("operation", ["read", "write"])
def test_path_traversal_is_rejected(sandbox_root: Path, operation: str) -> None:
    if operation == "read":
        with pytest.raises(sandbox_fs.SandboxViolation):
            sandbox_fs.read_text("traversal-session", "../../../etc/passwd")
    else:
        with pytest.raises(sandbox_fs.SandboxViolation):
            sandbox_fs.write_text("traversal-session", "../../../escape.txt", "blocked")

    assert not sandbox_root.exists()


def test_symlink_escape_is_rejected(sandbox_root: Path, tmp_path: Path) -> None:
    session_id = "symlink-session"
    sandbox_fs.write_text(session_id, "inside.txt", "safe")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")
    (sandbox_root / session_id / "escape.txt").symlink_to(outside_file)

    with pytest.raises(sandbox_fs.SandboxViolation):
        sandbox_fs.read_text(session_id, "escape.txt")


def test_symlinked_session_root_is_rejected(sandbox_root: Path) -> None:
    real_session = sandbox_root / "real-session"
    real_session.mkdir(parents=True)
    (sandbox_root / "aliased-session").symlink_to(real_session, target_is_directory=True)

    with pytest.raises(sandbox_fs.SandboxViolation):
        sandbox_fs.list_dir("aliased-session", ".")


def test_world_writable_mode_is_rejected(sandbox_root: Path) -> None:
    with pytest.raises(sandbox_fs.SandboxViolation):
        sandbox_fs.write_text("mode-session", "unsafe.txt", "blocked", mode=0o602)

    assert not sandbox_root.exists()


def test_sandbox_root_uses_sc_evm_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured_root = tmp_path / "configured-sandboxes"
    monkeypatch.setenv("SC_EVM_SANDBOX_ROOT", str(configured_root))

    configured = Settings(_env_file=None)

    assert configured.SANDBOX_ROOT == configured_root


def test_api_burn_rejects_nonexistent_session(sandbox_root: Path) -> None:
    response = post_to_app("/api/session/burn/missing-session")

    assert response.status_code == 400
    assert response.json() == {"detail": "Session not found"}
    assert not sandbox_root.exists()


def test_api_burn_rejects_invalid_session_identifier(sandbox_root: Path) -> None:
    response = post_to_app("/api/session/burn/invalid%24session")

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid session identifier"}
    assert not sandbox_root.exists()
