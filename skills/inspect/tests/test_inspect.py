"""Tests for inspect skill scripts."""

from __future__ import annotations

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


def test_info():
    result = run_script(SCRIPTS / "info.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "inspect.info"
    assert data["data"]["read_only"] is True


def test_probe(sample_video: Path):
    result = run_script(SCRIPTS / "probe.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "inspect.probe"
    assert "streams" in data["data"]


def test_describe(sample_video: Path):
    result = run_script(SCRIPTS / "describe.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["video"]["width"] == 320


def test_duration(sample_video: Path):
    result = run_script(SCRIPTS / "duration.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert 1.5 <= data["data"]["duration_seconds"] <= 2.5


def test_resolution(sample_video: Path):
    result = run_script(SCRIPTS / "resolution.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["width"] == 320
    assert data["data"]["height"] == 240


def test_compare(sample_video: Path, tmp_path: Path):
    copy = tmp_path / "copy.mp4"
    copy.write_bytes(sample_video.read_bytes())
    result = run_script(
        SCRIPTS / "compare.py",
        "--input-a",
        str(sample_video),
        "--input-b",
        str(copy),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert "a" in data["data"] and "b" in data["data"]


def test_batch_probe(sample_video: Path, sample_audio: Path):
    result = run_script(
        SCRIPTS / "batch_probe.py",
        "--paths",
        str(sample_video),
        str(sample_audio),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert len(data["data"]["rows"]) == 2


def test_ask(sample_video: Path):
    result = run_script(
        SCRIPTS / "ask.py",
        "--input",
        str(sample_video),
        "--question",
        "What is the resolution?",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["question"] == "What is the resolution?"
