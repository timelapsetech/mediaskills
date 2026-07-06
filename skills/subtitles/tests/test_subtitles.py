"""Tests for subtitles skill scripts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
from tests.helpers import parse_json_stdout, run_script  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:02,000
Hello world.

2
00:00:02,000 --> 00:00:04,000
Second line.
"""

SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
Hello world.

00:00:02.000 --> 00:00:04.000
Second line.
"""


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg/ffprobe not available")
    media_dir = tmp_path / "media"
    media_dir.mkdir(exist_ok=True)
    path = media_dir / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    import subprocess

    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


@pytest.fixture
def sample_srt(tmp_path: Path) -> Path:
    path = tmp_path / "sample.srt"
    path.write_text(SAMPLE_SRT, encoding="utf-8")
    return path


@pytest.fixture
def sample_vtt(tmp_path: Path) -> Path:
    path = tmp_path / "sample.vtt"
    path.write_text(SAMPLE_VTT, encoding="utf-8")
    return path


def test_convert_srt_to_vtt(sample_srt: Path, tmp_path: Path):
    out = tmp_path / "out.vtt"
    result = run_script(
        SCRIPTS / "convert.py",
        "--input",
        str(sample_srt),
        "--format",
        "vtt",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "subtitles.convert"
    assert data["data"]["cue_count"] == 2
    content = out.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT")
    assert "Hello world." in content


def test_convert_vtt_to_srt(sample_vtt: Path, tmp_path: Path):
    out = tmp_path / "out.srt"
    result = run_script(
        SCRIPTS / "convert.py",
        "--input",
        str(sample_vtt),
        "--format",
        "srt",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["cue_count"] == 2
    assert "Hello world." in out.read_text(encoding="utf-8")


def test_shift(sample_srt: Path, tmp_path: Path):
    out = tmp_path / "shifted.srt"
    result = run_script(
        SCRIPTS / "shift.py",
        "--input",
        str(sample_srt),
        "--offset-seconds",
        "1.5",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["offset_seconds"] == 1.5
    text = out.read_text(encoding="utf-8")
    assert "00:00:01,500 --> 00:00:03,500" in text


def test_extract_no_subtitle_track(sample_video: Path, tmp_path: Path):
    out = tmp_path / "extracted.srt"
    result = run_script(
        SCRIPTS / "extract.py",
        "--input",
        str(sample_video),
        "--output",
        str(out),
    )
    assert result.returncode != 0
    err = json.loads(result.stderr.strip().splitlines()[-1])
    assert err["ok"] is False
    assert err["op"] == "subtitles.extract"


def test_burn(sample_video: Path, sample_srt: Path, tmp_path: Path):
    out = tmp_path / "burned.mp4"
    result = run_script(
        SCRIPTS / "burn.py",
        "--input",
        str(sample_video),
        "--subtitle",
        str(sample_srt),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "subtitles.burn"
    assert out.is_file()
    assert out.stat().st_size > 0
    assert data["data"]["cue_count"] == 2
