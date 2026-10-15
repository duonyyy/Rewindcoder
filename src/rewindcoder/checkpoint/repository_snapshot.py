"""Capture and restore Git-visible workspace bytes without Git reset/clean."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class SnapshotError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "--no-pager", *args], cwd=root, capture_output=True, timeout=15,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
             "GIT_TERMINAL_PROMPT": "0", "GIT_EXTERNAL_DIFF": "", "GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode:
        raise SnapshotError(f"Git {' '.join(args)} failed: {result.stderr.decode(errors='replace')[-500:]}")
    return result.stdout


def validate_name(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise SnapshotError("invalid workspace path")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or not relative.parts or name != relative.as_posix()
            or any(part in (".", "..", "") for part in relative.parts)
            or relative.parts[0].casefold() == ".git"):
        raise SnapshotError("path traversal or Git internals denied")
    return relative


def safe_path(root: Path, name: str) -> Path:
    relative = validate_name(name)
    target = root.joinpath(*relative.parts)
    if not target.resolve(strict=False).is_relative_to(root):
        raise SnapshotError("path escapes workspace")
    for parent in (target, *target.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise SnapshotError("symlink path denied")
    return target


def _names(root: Path, *args: str) -> tuple[str, ...]:
    names = tuple(os.fsdecode(item) for item in git(root, "ls-files", *args).split(b"\0") if item)
    if len({name.casefold() for name in names}) != len(names):
        raise SnapshotError("case-colliding paths denied")
    for name in names:
        safe_path(root, name)
    return tuple(sorted(names))


def inventory(root: Path) -> dict:
    root = root.resolve(strict=True)
    if Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
        raise SnapshotError("workspace must be Git root")
    tracked = _names(root, "--cached", "-z")
    untracked = _names(root, "--others", "--exclude-standard", "-z")
    if set(tracked) & set(untracked):
        raise SnapshotError("tracked/untracked overlap")
    hashes: dict[str, str | None] = {}
    modes: dict[str, int] = {}
    for name in (*tracked, *untracked):
        path = safe_path(root, name)
        if path.exists():
            if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
                raise SnapshotError("non-regular file denied")
            data = path.read_bytes()
            hashes[name] = sha256(data)
            modes[name] = stat.S_IMODE(path.stat().st_mode)
        elif name in tracked:
            hashes[name] = None
        else:
            raise SnapshotError("untracked file disappeared during capture")
    return {"tracked": list(tracked), "untracked": list(untracked), "hashes": hashes, "modes": modes}


def git_diff_hash(root: Path) -> str:
    return sha256(git(root, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"))


def capture(root: Path, archive: Path) -> dict:
    before = inventory(root)
    if git(root, "diff", "--cached", "--name-only", "--").strip():
        raise SnapshotError("staged changes are not supported by the Phase 3 snapshot")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, digest in before["hashes"].items():
            if digest is not None:
                bundle.write(safe_path(root, name), arcname=name)
    after = inventory(root)
    if before != after:
        raise SnapshotError("workspace changed during capture")
    return before


def archive_bytes(archive: Path, manifest: dict) -> dict[str, bytes]:
    expected = {name: digest for name, digest in manifest["hashes"].items() if digest is not None}
    contents: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(archive) as bundle:
            if len(bundle.infolist()) != len(expected):
                raise SnapshotError("archive entry count mismatch")
            for entry in bundle.infolist():
                name = entry.filename
                if name not in expected or name in contents:
                    raise SnapshotError("unexpected or duplicate archive path")
                if (entry.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                    raise SnapshotError("archive symlink denied")
                data = bundle.read(entry)
                if sha256(data) != expected[name]:
                    raise SnapshotError("archive content hash mismatch")
                contents[name] = data
    except (zipfile.BadZipFile, OSError, RuntimeError) as error:
        raise SnapshotError("archive missing or corrupt") from error
    return contents


def restore(root: Path, archive: Path, manifest: dict) -> None:
    """Prevalidate all archive bytes and paths before changing the workspace."""
    root = root.resolve(strict=True)
    contents = archive_bytes(archive, manifest)
    current = inventory(root)
    names = set(current["hashes"]) | set(manifest["hashes"])
    for name in names:
        safe_path(root, name)
    for name in names - set(contents):
        path = safe_path(root, name)
        if path.is_file():
            path.unlink()
    for name, data in contents.items():
        path = safe_path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        os.chmod(path, manifest["modes"][name])
