"""Tests for vision-analysis skill scripts."""

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

sys.path.insert(0, str(SCRIPTS))
from _forced_narrative_lib import build_dialogue_rows_from_analysis  # noqa: E402
from _report_lib import (  # noqa: E402
    build_condensed_rows,
    condense_text_rows,
    frame_on_screen_items,
    refine_text_type,
)


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


@pytest.fixture
def sample_manifest(tmp_path: Path, sample_video: Path) -> Path:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    frames = []
    for i in range(3):
        frame_path = frames_dir / f"frame_{i:06d}.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=1:size=160x120:rate=1",
                "-frames:v",
                "1",
                str(frame_path),
            ],
            check=True,
            capture_output=True,
        )
        frames.append(
            {
                "index": i,
                "time_seconds": float(i),
                "start_seconds": float(i),
                "end_seconds": float(i + 1),
                "start_timecode": f"00:00:0{i}:00",
                "end_timecode": f"00:00:0{i + 1}:00",
                "frame_path": str(frame_path),
                "path": str(frame_path),
            }
        )
    manifest = {
        "input_path": str(sample_video.resolve()),
        "sequence_type": "interval",
        "interval_seconds": 1.0,
        "duration_seconds": 3.0,
        "fps": 30.0,
        "frames_dir": str(frames_dir),
        "frames": frames,
        "frame_count": len(frames),
    }
    manifest_path = tmp_path / "sample_interval_frames.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


@pytest.fixture
def sample_analysis(sample_manifest: Path, sample_video: Path) -> Path:
    analysis = {
        "manifest_path": str(sample_manifest),
        "input_path": str(sample_video.resolve()),
        "frame_count": 3,
        "analyzed_count": 2,
        "fps": 30.0,
        "frames": [
            {
                "index": 0,
                "shot_index": 0,
                "start_seconds": 0.0,
                "end_seconds": 1.0,
                "start_timecode": "00:00:00:00",
                "end_timecode": "00:00:01:00",
                "description": "A news anchor at a desk.",
                "keywords": ["news", "studio"],
                "on_screen_text": [
                    {
                        "text": "Breaking News",
                        "text_type": "lower_third",
                        "location": "bottom",
                        "confidence": 0.9,
                    }
                ],
            },
            {
                "index": 1,
                "shot_index": 1,
                "start_seconds": 1.0,
                "end_seconds": 2.0,
                "start_timecode": "00:00:01:00",
                "end_timecode": "00:00:02:00",
                "description": "Interview outdoors.",
                "keywords": ["interview"],
                "on_screen_text": [
                    {
                        "text": "OFFICER: We need to leave the property now.",
                        "text_type": "subtitle",
                        "location": "bottom",
                        "confidence": 0.95,
                    }
                ],
            },
            {
                "index": 2,
                "shot_index": 2,
                "start_seconds": 2.0,
                "end_seconds": 3.0,
                "start_timecode": "00:00:02:00",
                "end_timecode": "00:00:03:00",
                "description": "Title card.",
                "keywords": ["title"],
                "on_screen_text": [
                    {
                        "text": "Episode One",
                        "text_type": "title",
                        "location": "center",
                        "confidence": 0.98,
                    }
                ],
            },
        ],
    }
    path = sample_manifest.parent / "sample_frame_analysis.json"
    path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    return path


def test_analysis_schema():
    result = run_script(SCRIPTS / "analysis_schema.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "vision.analysis_schema"
    assert "frames" in data["data"]["properties"]


def test_get_frame_batch(sample_manifest: Path):
    result = run_script(
        SCRIPTS / "get_frame_batch.py",
        "--manifest-path",
        str(sample_manifest),
        "--batch-size",
        "2",
        "--batch-index",
        "0",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert len(data["data"]["frames"]) == 2
    assert data["data"]["has_more"] is True


def test_list_extractions():
    result = run_script(SCRIPTS / "list_extractions.py")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert "items" in data["data"]


def test_report_lib_filters_scene_description():
    items = frame_on_screen_items(
        {
            "description": "A man wading in a river.",
            "on_screen_text": [{"text": "A man wading in a river.", "text_type": "subtitle"}],
        }
    )
    assert items == []


def test_report_lib_refine_dialogue_to_subtitle():
    assert refine_text_type("We have to go now.", "lower_third") == "subtitle"


def test_condense_text_rows():
    rows = [
        {
            "text": "Hello",
            "text_type": "subtitle",
            "start_seconds": 0.0,
            "end_seconds": 1.0,
        },
        {
            "text": "Hello",
            "text_type": "subtitle",
            "start_seconds": 1.5,
            "end_seconds": 2.0,
        },
    ]
    merged = condense_text_rows(rows, fps=30.0)
    assert len(merged) == 1
    assert merged[0]["end_seconds"] == 2.0


def test_text_on_screen_report(sample_analysis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    gen = tmp_path / "generated"
    gen.mkdir()
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "text_on_screen_report.py",
        "--analysis-path",
        str(sample_analysis),
        "--force",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["row_count"] >= 1
    assert Path(data["data"]["report_path"]).is_file()


def test_forced_narrative_report(sample_analysis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "forced_narrative_report.py",
        "--analysis-path",
        str(sample_analysis),
        "--force",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    analysis = json.loads(sample_analysis.read_text())
    rows = build_dialogue_rows_from_analysis(analysis)
    assert data["data"]["row_count"] == len(rows)
    assert data["data"]["row_count"] >= 1


def test_graphics_on_screen_report(sample_analysis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "graphics_on_screen_report.py",
        "--analysis-path",
        str(sample_analysis),
        "--force",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["row_count"] >= 1


def test_extract_title_text(sample_analysis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "extract_title_text.py",
        "--analysis-path",
        str(sample_analysis),
        "--force",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["text_count"] >= 1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not available")
def test_extract_interval_frames(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "extract_interval_frames.py",
        "--input",
        str(sample_video),
        "--interval",
        "1",
        "--max-frames",
        "3",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["frame_count"] >= 1
    manifest = Path(data["data"]["manifest_path"])
    assert manifest.is_file()


def test_merge_analysis(sample_manifest: Path, tmp_path: Path):
    batch = {
        "frames": [
            {
                "index": 0,
                "description": "Test pattern frame.",
                "keywords": ["test"],
                "on_screen_text": [],
            }
        ]
    }
    batch_path = tmp_path / "batch0.json"
    batch_path.write_text(json.dumps(batch), encoding="utf-8")
    analysis_path = tmp_path / "analysis.json"
    result = run_script(
        SCRIPTS / "merge_analysis.py",
        "--manifest-path",
        str(sample_manifest),
        "--frames-json",
        str(batch_path),
        "--analysis-path",
        str(analysis_path),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert analysis_path.is_file()
    assert data["data"]["merged_frames"] == 1


def test_validate_analysis(sample_analysis: Path):
    result = run_script(
        SCRIPTS / "validate_analysis.py",
        "--analysis-path",
        str(sample_analysis),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["valid"] is True


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not available")
def test_prepare_manifest(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "prepare_manifest.py",
        "--input",
        str(sample_video),
        "--interval",
        "1",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "vision.prepare_manifest"
    assert data["data"]["frame_count"] >= 1
    assert Path(data["data"]["manifest_path"]).is_file()


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not available")
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not available")
def test_compile_report(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "compile_report.py",
        "--input",
        str(sample_video),
        "--interval",
        "1",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "vision.compile_report"
    assert Path(data["data"]["json_path"]).is_file()
    assert Path(data["data"]["report_path"]).is_file()


def test_compile_all_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    gen = tmp_path / "generated"
    gen.mkdir()
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    report = gen / "clip_onscreen_text_20260101_1234.json"
    report.write_text(
        json.dumps(
            {
                "input_path": "/tmp/clip.mp4",
                "detection_count": 2,
                "rows": [],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "index.md"
    result = run_script(
        SCRIPTS / "compile_all_reports.py",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "vision.compile_all_reports"
    assert data["data"]["count"] >= 1
    assert out.is_file()
