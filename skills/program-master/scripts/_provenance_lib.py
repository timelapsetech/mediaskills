"""Build deterministic provenance records for program-master artifacts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

SKILL_VERSION = "2.0.0"
MANIFEST_SCHEMA_VERSION = "2.0"
REPORT_SCHEMA_VERSION = "2.0"


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def command_version(command: str) -> str | None:
    try:
        proc = subprocess.run(
            [command, "--version"] if command == "tesseract" else [command, "-version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    return text.splitlines()[0] if text else None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def build_provenance(
    source: Path,
    *,
    profile: dict[str, Any],
    profile_path: Path,
    selected_streams: dict[str, Any],
    command: list[str],
) -> dict[str, Any]:
    stat = source.stat()
    return {
        "skill": {"name": "program-master", "version": SKILL_VERSION},
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source": {
            "path": str(source.resolve()),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256_file(source),
        },
        "profile": {
            "path": str(profile_path),
            "name": profile.get("name"),
            "version": profile.get("profile_version"),
            "sha256": sha256_json(profile),
        },
        "selected_streams": selected_streams,
        "toolchain": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "ffmpeg": command_version("ffmpeg"),
            "ffprobe": command_version("ffprobe"),
            "tesseract": command_version("tesseract"),
            "timecode": package_version("timecode"),
            "reportlab": package_version("reportlab"),
            "pypdf": package_version("pypdf"),
        },
        "command": [str(part) for part in command],
        "python_executable": sys.executable,
    }
