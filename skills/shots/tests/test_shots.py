"""Tests for shots skill scripts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
from tests.helpers import parse_json_stdout, run_script  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


def test_detect(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(SCRIPTS / "detect.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "shots.detect"
    assert data["data"]["shot_count"] >= 1
    manifest = Path(data["data"]["manifest_path"])
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["shots"]
    assert payload["duration_seconds"] > 0


def test_extract_frames_from_manifest(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    detect = run_script(SCRIPTS / "detect.py", "--input", str(sample_video))
    assert detect.returncode == 0, detect.stderr
    shots_path = parse_json_stdout(detect)["data"]["manifest_path"]

    result = run_script(
        SCRIPTS / "extract-frames.py",
        "--shots-path",
        shots_path,
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "shots.extract_frames"
    assert data["data"]["frame_count"] >= 1
    frames_dir = Path(data["data"]["frames_dir"])
    assert frames_dir.is_dir()
    assert any(frames_dir.glob("shot_*.jpg"))


def test_extract_frames_inline(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "extract-frames.py",
        "--input",
        str(sample_video),
        "--max-frames",
        "5",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["frame_count"] >= 1
