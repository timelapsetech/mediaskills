"""Tests for video-transformation skill scripts."""

from __future__ import annotations

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


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    if not has_cmd("ffmpeg"):
        pytest.skip("ffmpeg/ffprobe not available")
    media_dir = tmp_path / "media"
    media_dir.mkdir(exist_ok=True)
    path = media_dir / "sample.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
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
def generated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    gen = tmp_path / "generated"
    gen.mkdir()
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return gen


def test_info():
    result = run_script(SCRIPTS / "info.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "video.info"
    assert "trim" in data["data"]["operations"]


def test_trim(sample_video: Path, generated_cwd: Path):
    out = generated_cwd / "trimmed.mp4"
    result = run_script(
        SCRIPTS / "trim.py",
        "--input",
        str(sample_video),
        "--start",
        "0.5",
        "--end",
        "1.5",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


def test_trim_multi(sample_video: Path, generated_cwd: Path):
    result = run_script(
        SCRIPTS / "trim_multi.py",
        "--input",
        str(sample_video),
        "--segment",
        "0:0.8",
        "--segment",
        "1.2:1.8",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["segment_count"] == 2
    for p in data["output_paths"]:
        assert Path(p).is_file()


def test_concat(sample_video: Path, generated_cwd: Path):
    seg_a = generated_cwd / "a.mp4"
    seg_b = generated_cwd / "b.mp4"
    for start, end, dest in [("0", "0.8", seg_a), ("1.0", "1.8", seg_b)]:
        r = run_script(
            SCRIPTS / "trim.py",
            "--input",
            str(sample_video),
            "--start",
            start,
            "--end",
            end,
            "--output",
            str(dest),
        )
        assert r.returncode == 0, r.stderr
    out = generated_cwd / "joined.mp4"
    result = run_script(
        SCRIPTS / "concat.py",
        "--paths",
        str(seg_a),
        str(seg_b),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["input_count"] == 2
    assert out.is_file()


def test_transcode(sample_video: Path, generated_cwd: Path):
    out = generated_cwd / "transcoded.mp4"
    result = run_script(
        SCRIPTS / "transcode.py",
        "--input",
        str(sample_video),
        "--output",
        str(out),
        "--codec",
        "libx264",
        "--crf",
        "28",
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_scale(sample_video: Path, generated_cwd: Path):
    out = generated_cwd / "scaled.mp4"
    result = run_script(
        SCRIPTS / "scale.py",
        "--input",
        str(sample_video),
        "--width",
        "160",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_proxy(sample_video: Path, generated_cwd: Path):
    out = generated_cwd / "proxy.mp4"
    result = run_script(
        SCRIPTS / "proxy.py",
        "--input",
        str(sample_video),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_extract_frame(sample_video: Path, generated_cwd: Path):
    out = generated_cwd / "frame.jpg"
    result = run_script(
        SCRIPTS / "extract_frame.py",
        "--input",
        str(sample_video),
        "--time",
        "1.0",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["time_seconds"] == pytest.approx(1.0, abs=0.01)
    assert out.is_file() and out.stat().st_size > 0


def test_extract_audio(sample_video: Path, generated_cwd: Path):
    out = generated_cwd / "audio.mp3"
    result = run_script(
        SCRIPTS / "extract_audio.py",
        "--input",
        str(sample_video),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_to_gif(sample_video: Path, generated_cwd: Path):
    out = generated_cwd / "clip.gif"
    result = run_script(
        SCRIPTS / "to_gif.py",
        "--input",
        str(sample_video),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_replace_audio(sample_video: Path, sample_audio: Path, generated_cwd: Path):
    out = generated_cwd / "muxed.mp4"
    result = run_script(
        SCRIPTS / "replace_audio.py",
        "--input",
        str(sample_video),
        "--audio",
        str(sample_audio),
        "--output",
        str(out),
        "--copy-video",
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()
