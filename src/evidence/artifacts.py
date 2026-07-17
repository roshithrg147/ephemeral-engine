from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ImmutableArtifactStore:
    def __init__(self, root: Path, run_id: str):
        self.run_dir = root / run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        for name in ("raw", "evaluations", "traces"):
            (self.run_dir / name).mkdir()

    def write_json(self, relative: str, value: Any) -> Path:
        path = self.run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        return path

    def write_text(self, relative: str, value: str) -> Path:
        path = self.run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
        return path

    def write_checksums(self) -> Path:
        files = sorted(
            path
            for path in self.run_dir.rglob("*")
            if path.is_file() and path.name != "checksums.sha256"
        )
        lines = [f"{sha256_file(path)}  {path.relative_to(self.run_dir)}" for path in files]
        return self.write_text("checksums.sha256", "\n".join(lines) + "\n")

    def validate_checksums(self) -> bool:
        checksum_path = self.run_dir / "checksums.sha256"
        if not checksum_path.is_file():
            return False
        expected = {
            path.relative_to(self.run_dir).as_posix()
            for path in self.run_dir.rglob("*")
            if path.is_file() and path != checksum_path
        }
        seen = set()
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            try:
                digest, relative = line.split("  ", 1)
            except ValueError:
                return False
            candidate = Path(relative)
            if candidate.is_absolute() or ".." in candidate.parts or relative in seen:
                return False
            target = self.run_dir / candidate
            if not target.is_file() or sha256_file(target) != digest:
                return False
            seen.add(candidate.as_posix())
        return seen == expected
