"""Semantic ground-truth tests for high-risk skills (local smoke)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
from tests.helpers import parse_json_stdout, run_script, sync_shared_libs  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _sync():
    sync_shared_libs()


def _ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def _ffprobe_size(path: Path) -> tuple[int, int]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_trim_duration_matches_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    video = FIXTURES / "sample.mp4"
    assert video.is_file()
    out = tmp_path / "generated" / "trimmed.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    result = run_script(
        REPO_ROOT / "skills/video-transformation/scripts/trim.py",
        "--input",
        str(video),
        "--start",
        "0.2",
        "--end",
        "0.8",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()
    duration = _ffprobe_duration(out)
    assert duration == pytest.approx(0.6, abs=0.2)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_scale_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    video = FIXTURES / "sample.mp4"
    out = tmp_path / "generated" / "scaled.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    result = run_script(
        REPO_ROOT / "skills/video-transformation/scripts/scale.py",
        "--input",
        str(video),
        "--width",
        "160",
        "--height",
        "120",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    assert parse_json_stdout(result)["ok"] is True
    width, height = _ffprobe_size(out)
    assert width == 160
    assert height == 120


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_shots_three_hard_cuts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    video = FIXTURES / "cuts_3scene.mp4"
    meta = json.loads((FIXTURES / "cuts_3scene.meta.json").read_text(encoding="utf-8"))
    assert video.is_file()
    result = run_script(
        REPO_ROOT / "skills/shots/scripts/detect.py",
        "--input",
        str(video),
        "--threshold",
        "0.3",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["shot_count"] == meta["expected_shot_count"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_program_gaps_black_silence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    video = FIXTURES / "program_gaps.mp4"
    meta = json.loads((FIXTURES / "program_gaps.meta.json").read_text(encoding="utf-8"))
    assert video.is_file()
    result = run_script(
        REPO_ROOT / "skills/program-master/scripts/detect_black_silence.py",
        "--input",
        str(video),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert int(data["data"]["gap_count"]) >= int(meta["expected_min_gap_count"])


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_verify_output_helper_duration(tmp_path: Path):
    video = FIXTURES / "sample.mp4"
    envelope = {
        "ok": True,
        "op": "test.fixture",
        "data": {},
        "output_paths": [str(video)],
    }
    env_path = tmp_path / "envelope.json"
    env_path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/verify_output.py"),
            "--from-json",
            str(env_path),
            "--min-duration",
            "0.8",
            "--max-duration",
            "1.3",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1])["ok"] is True
