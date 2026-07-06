"""Tests for speech-captions skill scripts."""

from __future__ import annotations

import json
import os
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


@pytest.mark.skipif(
    not os.environ.get("MEDIASKILLS_RUN_WHISPER"),
    reason="Set MEDIASKILLS_RUN_WHISPER=1 to run faster-whisper integration tests",
)
def test_transcribe(sample_audio: Path, tmp_path: Path):
    out = tmp_path / "transcript.srt"
    result = run_script(
        SCRIPTS / "transcribe.py",
        "--input",
        str(sample_audio),
        "--model",
        "tiny",
        "--output",
        str(out),
        "--json-output",
        str(tmp_path / "transcript.json"),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "speech_captions.transcribe"
    assert out.is_file()


@pytest.mark.skipif(
    not os.environ.get("MEDIASKILLS_RUN_WHISPER"),
    reason="Set MEDIASKILLS_RUN_WHISPER=1 to run faster-whisper integration tests",
)
def test_detect_language(sample_audio: Path):
    result = run_script(
        SCRIPTS / "detect-language.py",
        "--input",
        str(sample_audio),
        "--sample-seconds",
        "2",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "speech_captions.detect_language"
    assert "language" in data["data"]


def test_to_srt_from_text(tmp_path: Path):
    out = tmp_path / "out.srt"
    result = run_script(
        SCRIPTS / "to-srt.py",
        "--text",
        "Hello world.",
        "--duration",
        "5",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "speech_captions.to_srt"
    assert out.is_file()
    assert "Hello world." in out.read_text(encoding="utf-8")


def test_to_vtt_from_segments(tmp_path: Path):
    segments_path = tmp_path / "segments.json"
    segments_path.write_text(
        json.dumps(
            [
                {"start": 0.0, "end": 2.0, "text": "First line."},
                {"start": 2.0, "end": 4.0, "text": "Second line."},
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.vtt"
    result = run_script(
        SCRIPTS / "to-vtt.py",
        "--segments-json",
        str(segments_path),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "speech_captions.to_vtt"
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "WEBVTT" in content
    assert "First line." in content
