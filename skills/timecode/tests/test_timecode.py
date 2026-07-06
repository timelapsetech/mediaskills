"""Tests for timecode skill scripts."""

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


def has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    if not has_cmd("ffmpeg"):
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
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


def test_info():
    result = run_script(SCRIPTS / "info.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "timecode.info"
    assert "29.97" in [str(x) for x in data["data"]["supported_fps"]]


def test_to_seconds_ndf():
    result = run_script(
        SCRIPTS / "to_seconds.py",
        "--timecode",
        "00:01:00:00",
        "--fps",
        "30",
        "--non-drop-frame",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["seconds"] == pytest.approx(60.0)
    assert data["data"]["frames"] == 1800
    assert data["data"]["drop_frame"] is False


def test_to_seconds_drop_frame():
    result = run_script(
        SCRIPTS / "to_seconds.py",
        "--timecode",
        "00:10:00;00",
        "--fps",
        "29.97",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["drop_frame"] is True
    assert ";" in data["data"]["timecode"]


def test_from_seconds():
    result = run_script(
        SCRIPTS / "from_seconds.py",
        "--seconds",
        "60",
        "--fps",
        "30",
        "--non-drop-frame",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["timecode"] == "00:01:00:00"


def test_calculate_add():
    result = run_script(
        SCRIPTS / "calculate.py",
        "--timecode",
        "00:01:00:00",
        "--op",
        "add",
        "--offset-seconds",
        "5",
        "--fps",
        "30",
        "--non-drop-frame",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["seconds"] == pytest.approx(65.0)


def test_calculate_sub():
    result = run_script(
        SCRIPTS / "calculate.py",
        "--timecode",
        "00:01:00:00",
        "--op",
        "sub",
        "--offset-seconds",
        "10",
        "--fps",
        "30",
        "--non-drop-frame",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["seconds"] == pytest.approx(50.0)


def test_convert():
    result = run_script(
        SCRIPTS / "convert.py",
        "--timecode",
        "00:01:00:00",
        "--from-fps",
        "24",
        "--to-fps",
        "30",
        "--non-drop-frame",
        "--target-non-drop-frame",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["seconds_realtime"] == pytest.approx(
        data["data"]["source"]["seconds_realtime"],
        abs=0.05,
    )


def test_convert_df():
    result = run_script(
        SCRIPTS / "convert_df.py",
        "--timecode",
        "01:00:00;00",
        "--fps",
        "29.97",
        "--to",
        "non-drop-frame",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["drop_frame"] is False
    assert ":" in data["data"]["timecode"]
    assert data["data"]["seconds_realtime"] == pytest.approx(
        data["data"]["source"]["seconds_realtime"],
        abs=0.001,
    )


def test_detect_format_semicolon():
    result = run_script(
        SCRIPTS / "detect_format.py",
        "--timecode",
        "01:00:00;00",
        "--fps",
        "29.97",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "timecode.detect_format"
    assert data["data"]["inferred_drop_frame"] is True
    assert data["data"]["delimiter"] == ";"


def test_analyze_metadata(tmp_path: Path):
    meta = {
        "format": {"tags": {"timecode": "01:00:00;00"}},
        "streams": [{"codec_type": "video", "avg_frame_rate": "30000/1001"}],
    }
    path = tmp_path / "meta.json"
    path.write_text(json.dumps(meta), encoding="utf-8")
    result = run_script(SCRIPTS / "analyze_metadata.py", "--input", str(path))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["inferred_drop_frame"] is True


def test_extract(sample_video: Path):
    result = run_script(SCRIPTS / "extract.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "timecode.extract"
    assert "duration_seconds" in data["data"]
    assert data["data"]["duration_seconds"] == pytest.approx(2.0, abs=0.2)
