"""Tests for program-master skill scripts."""

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


def test_schema():
    result = run_script(SCRIPTS / "schema.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "program_master.schema"
    assert data["data"]["type"] == "object"
    assert "segments" in data["data"]["properties"]


def test_detect_blacks(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(SCRIPTS / "detect_blacks.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "program_master.detect_blacks"
    assert "count" in data["data"]


def test_detect_silence(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(SCRIPTS / "detect_silence.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "program_master.detect_silence"
    assert "count" in data["data"]


def test_detect_black_silence(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(SCRIPTS / "detect_black_silence.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "program_master.detect_black_silence"
    assert "gap_count" in data["data"]


def test_analyze_structure(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(SCRIPTS / "analyze_structure.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "program_master.analyze_structure"
    assert data["data"]["segments"]


def test_label_segments(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(SCRIPTS / "label_segments.py", "--input", str(sample_video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "program_master.label_segments"
    assert data["data"]["segments"]
    manifest = Path(data["data"]["manifest_path"])
    assert manifest.is_file()


def test_compile(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    label = run_script(SCRIPTS / "label_segments.py", "--input", str(sample_video))
    assert label.returncode == 0, label.stderr
    structure_path = parse_json_stdout(label)["data"]["manifest_path"]

    result = run_script(
        SCRIPTS / "compile.py",
        "--structure-path",
        structure_path,
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "program_master.compile"
    md = Path(data["data"]["output_path"])
    json_path = Path(data["data"]["json_path"])
    assert md.is_file()
    assert json_path.is_file()
    assert "# Program master:" in md.read_text(encoding="utf-8")
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["rows"]
    assert data["data"]["segment_count"] == len(report["rows"])
