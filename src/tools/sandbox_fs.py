"""Path-traversal-protected filesystem operations for session sandboxes."""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from src.config import settings

logger = logging.getLogger("SC-EVM.SandboxFS")

_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class SandboxViolation(RuntimeError):
    """Raised when a requested filesystem operation escapes its session sandbox."""


@dataclass(frozen=True, slots=True)
class SandboxBurnResult:
    """Filesystem deletion outcome used by the canonical lifecycle receipt."""

    existed: bool
    removed: bool


def _opaque_segment(kind: str, value: str) -> str:
    """Return a stable, non-reversible path segment for one ownership dimension."""
    if not value or not value.strip():
        raise SandboxViolation(f"Invalid {kind}")
    material = f"sc-evm-sandbox:{kind}\0{value}".encode()
    return sha256(material).hexdigest()


def _resolve_inside_root(requested: str, root: Path) -> Path:
    """Resolve a requested path and ensure it remains inside the supplied root."""
    resolved_root = root.resolve()
    candidate = (root / requested).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        logger.warning("Rejected sandbox path traversal", extra={"requested": requested})
        raise SandboxViolation("Requested path escapes the session sandbox") from exc
    return candidate


def _session_root(
    session_id: str,
    *,
    tenant_id: str = "development",
    owner_subject: str = "firebase:dev-firebase-uid",
) -> Path:
    """Return an opaque ownership-scoped session root."""
    if not _SESSION_ID_PATTERN.fullmatch(session_id):
        logger.warning("Rejected invalid sandbox session identifier")
        raise SandboxViolation("Invalid session identifier")

    from src.security.principal import IdentityCompatibilityResolver

    canonical_owner = IdentityCompatibilityResolver.normalize_owner_subject(owner_subject)
    sandbox_root = settings.SANDBOX_ROOT.resolve()
    segments = (
        _opaque_segment("tenant", tenant_id),
        _opaque_segment("subject", canonical_owner),
        _opaque_segment("session", session_id),
    )
    current = sandbox_root
    for segment in segments:
        current /= segment
        if current.is_symlink():
            logger.warning("Rejected symlinked sandbox ownership path")
            raise SandboxViolation("Sandbox ownership path must not be a symbolic link")
    return _resolve_inside_root("/".join(segments), sandbox_root)


def _ensure_directory(directory: Path, root: Path) -> None:
    """Create a directory tree and apply restrictive permissions to each new level."""
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    relative_parts = directory.relative_to(root).parts
    current = root
    for part in relative_parts:
        current /= part
        current.mkdir(exist_ok=True, mode=0o700)
        current.chmod(0o700)


def read_text(
    session_id: str,
    rel_path: str,
    *,
    tenant_id: str = "development",
    owner_subject: str = "firebase:dev-firebase-uid",
) -> str:
    """Read UTF-8 text from a file inside a session sandbox."""
    root = _session_root(session_id, tenant_id=tenant_id, owner_subject=owner_subject)
    target = _resolve_inside_root(rel_path, root)
    content = target.read_bytes().decode("utf-8")
    logger.info("Read sandbox file", extra={"session_id": session_id, "path": rel_path})
    return content


def write_text(
    session_id: str,
    rel_path: str,
    data: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o600,
    tenant_id: str = "development",
    owner_subject: str = "firebase:dev-firebase-uid",
) -> None:
    """Write text to a file inside a session sandbox with restrictive permissions."""
    if mode < 0 or mode > 0o777 or mode & 0o002:
        raise SandboxViolation("File mode must not be world-writable")

    root = _session_root(session_id, tenant_id=tenant_id, owner_subject=owner_subject)
    target = _resolve_inside_root(rel_path, root)
    _ensure_directory(target.parent, root)
    target.write_text(data, encoding=encoding)
    target.chmod(mode)
    logger.info("Wrote sandbox file", extra={"session_id": session_id, "path": rel_path})


def list_dir(
    session_id: str,
    rel_dir: str,
    *,
    tenant_id: str = "development",
    owner_subject: str = "firebase:dev-firebase-uid",
) -> list[str]:
    """List entry names in a directory inside a session sandbox."""
    root = _session_root(session_id, tenant_id=tenant_id, owner_subject=owner_subject)
    target = _resolve_inside_root(rel_dir, root)
    entries = sorted(entry.name for entry in target.iterdir())
    logger.info("Listed sandbox directory", extra={"session_id": session_id, "path": rel_dir})
    return entries


def burn_session(
    session_id: str,
    *,
    tenant_id: str = "development",
    owner_subject: str = "firebase:dev-firebase-uid",
) -> SandboxBurnResult:
    """Recursively remove one ownership-scoped filesystem sandbox."""
    sandbox_path = _session_root(
        session_id,
        tenant_id=tenant_id,
        owner_subject=owner_subject,
    )
    print("BURN_SESSION: path=", sandbox_path, "is_dir=", sandbox_path.is_dir())
    if not sandbox_path.is_dir():
        return SandboxBurnResult(existed=False, removed=False)

    shutil.rmtree(sandbox_path)
    print("BURN_SESSION: rmtree complete. Exists now?", sandbox_path.exists())
    for parent in (sandbox_path.parent, sandbox_path.parent.parent):
        try:
            parent.rmdir()
        except OSError:
            break
    logger.info("Burned ownership-scoped sandbox session")
    return SandboxBurnResult(existed=True, removed=True)
