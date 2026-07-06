"""Tests for download skill scripts."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
from tests.helpers import parse_json_stdout, run_script  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    import subprocess

    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


def test_missing_url():
    result = run_script(SCRIPTS / "url.py")
    assert result.returncode != 0


@pytest.mark.skipif(not shutil.which("yt-dlp"), reason="yt-dlp not available")
def test_url_help():
    result = run_script(SCRIPTS / "url.py", "--help")
    assert result.returncode == 0
    assert "--url" in result.stdout


@pytest.mark.skipif(
    not os.environ.get("MEDIASKILLS_RUN_NETWORK"),
    reason="Set MEDIASKILLS_RUN_NETWORK=1 for live URL metadata test",
)
@pytest.mark.skipif(not shutil.which("yt-dlp"), reason="yt-dlp not available")
def test_url_metadata_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "url.py",
        "--url",
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    )
    if result.returncode != 0:
        pytest.skip(f"network or yt-dlp blocked: {result.stderr[:200]}")
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "download.url"
