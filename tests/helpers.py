"""Shared test utilities for mediaskills skill scripts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_script(
    script_path: Path,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if shutil.which("uv"):
        cmd = ["uv", "run", str(script_path), *args]
    else:
        cmd = [sys.executable, str(script_path), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or script_path.parent)


def parse_json_stdout(result: subprocess.CompletedProcess[str]) -> dict:
    line = result.stdout.strip().splitlines()[-1]
    return json.loads(line)


def sync_shared_libs() -> None:
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )
