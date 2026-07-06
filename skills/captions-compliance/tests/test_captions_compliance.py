"""Tests for captions-compliance skill scripts."""

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

SAMPLE_SRT = """\
1
00:00:01,000 --> 00:00:04,000
Hello world.

2
00:00:05,000 --> 00:00:08,000
Second cue here.
"""

LONG_LINE_SRT = """\
1
00:00:01,000 --> 00:00:06,000
This is an intentionally very long caption line that should be wrapped or flagged by the formatting and busy-zone tools in this skill.
"""

OVERLAP_SRT = """\
1
00:00:01,000 --> 00:00:05,000
First cue.

2
00:00:04,000 --> 00:00:07,000
Overlapping cue.
"""


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
def long_line_srt(tmp_path: Path) -> Path:
    path = tmp_path / "long.srt"
    path.write_text(LONG_LINE_SRT, encoding="utf-8")
    return path


@pytest.fixture
def overlap_srt(tmp_path: Path) -> Path:
    path = tmp_path / "overlap.srt"
    path.write_text(OVERLAP_SRT, encoding="utf-8")
    return path


def test_info():
    result = run_script(SCRIPTS / "info.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "caption.info"
    assert "SCC" in str(data["data"]["exports"])


def test_rules():
    result = run_script(SCRIPTS / "rules.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "caption.rules"
    rules = {r["id"]: r for r in data["data"]["rules"]}
    assert rules["max_chars"]["value"] == 42
    assert rules["max_lines"]["value"] == 2


def test_validate_valid(sample_srt: Path):
    result = run_script(SCRIPTS / "validate.py", "--input", str(sample_srt))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "caption.validate"
    assert data["data"]["valid"] is True
    assert data["data"]["cue_count"] == 2


def test_validate_overlap(overlap_srt: Path):
    result = run_script(SCRIPTS / "validate.py", "--input", str(overlap_srt))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["data"]["valid"] is False
    assert any("overlaps" in issue for issue in data["data"]["issues"])


def test_validate_missing_input():
    result = run_script(SCRIPTS / "validate.py", "--input", "/nonexistent/file.srt")
    assert result.returncode != 0


def test_format_wraps_long_line(long_line_srt: Path, tmp_path: Path):
    out = tmp_path / "formatted.srt"
    result = run_script(
        SCRIPTS / "format.py",
        "--input",
        str(long_line_srt),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "\n" in text.split("-->")[1]
    assert data["data"]["cue_count"] == 1


def test_to_scc(sample_srt: Path, tmp_path: Path):
    out = tmp_path / "out.scc"
    result = run_script(
        SCRIPTS / "to-scc.py",
        "--input",
        str(sample_srt),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "caption.to_scc"
    assert data["data"]["valid"] is True
    content = out.read_text(encoding="utf-8")
    assert content.startswith("Scenarist_SCC V1.0")
    assert "\t" in content


def test_to_smpte_tt(sample_srt: Path, tmp_path: Path):
    out = tmp_path / "out.xml"
    result = run_script(
        SCRIPTS / "to-smpte-tt.py",
        "--input",
        str(sample_srt),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "caption.to_smpte_tt"
    content = out.read_text(encoding="utf-8")
    assert 'xmlns="http://www.w3.org/ns/ttml"' in content
    assert 'begin="00:00:01.000"' in content
    assert "Hello world." in content


def test_apply_busy_zones(long_line_srt: Path, tmp_path: Path):
    out = tmp_path / "busy.srt"
    result = run_script(
        SCRIPTS / "apply-busy-zones.py",
        "--input",
        str(long_line_srt),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["op"] == "caption.apply_busy_zones"
    assert data["data"]["flagged_count"] >= 1
    report_path = Path(data["data"]["report_path"])
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["count"] >= 1


def test_scc_unit_functions():
    sys.path.insert(0, str(SCRIPTS))
    import importlib

    to_scc = importlib.import_module("to-scc")
    rows = to_scc.split_rows("Hello broadcast captions")
    assert len(rows) >= 1
    assert to_scc.sanitize_text("“quote”") == '"quote"'
    content = to_scc.cues_to_scc(
        [{"start": 1.0, "end": 4.0, "text": "Test cue"}],
    )
    assert to_scc.validate_scc(content) == []


def test_validate_cues_unit():
    sys.path.insert(0, str(SCRIPTS))
    import importlib

    validate = importlib.import_module("validate")
    issues = validate.validate_cues([])
    assert "No cues parsed" in issues


def test_to_captions_pipeline_help():
    result = run_script(SCRIPTS / "to-captions-pipeline.py", "--help")
    assert result.returncode == 0
    assert "--input" in result.stdout
    assert "--model" in result.stdout


@pytest.mark.skipif(
    not os.environ.get("MEDIASKILLS_RUN_WHISPER"),
    reason="Set MEDIASKILLS_RUN_WHISPER=1 to run faster-whisper pipeline test",
)
def test_to_captions_pipeline(sample_video: Path, tmp_path: Path):
    out = tmp_path / "captions.srt"
    result = run_script(
        SCRIPTS / "to-captions-pipeline.py",
        "--input",
        str(sample_video),
        "--model",
        "tiny",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "caption.to_captions_pipeline"
    assert out.is_file()
