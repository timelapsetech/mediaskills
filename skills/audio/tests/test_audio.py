"""Tests for audio skill scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import parse_json_stdout, run_script

REPO_ROOT = Path(__file__).resolve().parents[3]

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


def test_probe(sample_audio: Path):
    result = run_script(SCRIPTS / "probe.py", "--input", str(sample_audio))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "audio.probe"
    assert "streams" in data["data"]


def test_extract(sample_video: Path, tmp_path: Path):
    out = tmp_path / "extracted.wav"
    result = run_script(
        SCRIPTS / "extract.py",
        "--input",
        str(sample_video),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()
    assert data["data"]["output_path"] == str(out)


def test_convert(sample_audio: Path, tmp_path: Path):
    out = tmp_path / "converted.mp3"
    result = run_script(
        SCRIPTS / "convert.py",
        "--input",
        str(sample_audio),
        "--format",
        "mp3",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


def test_trim(sample_audio: Path, tmp_path: Path):
    out = tmp_path / "trimmed.wav"
    result = run_script(
        SCRIPTS / "trim.py",
        "--input",
        str(sample_audio),
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


def test_concat(sample_audio: Path, tmp_path: Path):
    out = tmp_path / "joined.wav"
    result = run_script(
        SCRIPTS / "concat.py",
        "--paths",
        str(sample_audio),
        str(sample_audio),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


def test_normalize(sample_audio: Path, tmp_path: Path):
    out = tmp_path / "normalized.wav"
    result = run_script(
        SCRIPTS / "normalize.py",
        "--input",
        str(sample_audio),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


def test_fade(sample_audio: Path, tmp_path: Path):
    out = tmp_path / "faded.wav"
    result = run_script(
        SCRIPTS / "fade.py",
        "--input",
        str(sample_audio),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


def test_resample(sample_audio: Path, tmp_path: Path):
    out = tmp_path / "resampled.wav"
    result = run_script(
        SCRIPTS / "resample.py",
        "--input",
        str(sample_audio),
        "--sample-rate",
        "48000",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


def test_silence_detect(sample_audio: Path):
    result = run_script(SCRIPTS / "silence_detect.py", "--input", str(sample_audio))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "audio.silence_detect"
    assert "silence_starts" in data["data"]
    assert "silence_ends" in data["data"]
