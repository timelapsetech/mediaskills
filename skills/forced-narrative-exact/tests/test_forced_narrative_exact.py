"""Tests for forced-narrative-exact skill scripts."""

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


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


def test_scan_caption_band(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract not available")
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "scan_caption_band.py",
        "--input",
        str(sample_video),
        "--interval",
        "0.5",
        "--force",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "forced_narrative_exact.scan_caption_band"
    assert Path(data["data"]["output_path"]).is_file()
    assert Path(data["data"]["frames_dir"]).is_dir()


def test_build_and_validate_report(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate,nb_frames,duration,width,height",
            "-of",
            "json",
            str(sample_video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    fps = stream.get("avg_frame_rate") or "30/1"
    refined = {
        "schema_version": "1.0",
        "input_path": str(sample_video),
        "fps": fps,
        "drop_frame": False,
        "embedded_start_timecode": None,
        "crop": {"x": 0, "y": 160, "width": 320, "height": 80},
        "rows": [
            {
                "id": 1,
                "start_frame": 10,
                "end_frame_exclusive": 25,
                "speaker_context": "",
                "lines": ["HELLO"],
                "text": "HELLO",
            }
        ],
    }
    refined_path = tmp_path / "forced_narrative_refined.json"
    refined_path.write_text(json.dumps(refined, indent=2) + "\n", encoding="utf-8")

    build = run_script(
        SCRIPTS / "build_report.py",
        "--refined",
        str(refined_path),
        "--output-dir",
        str(tmp_path / "reports"),
        "--stem",
        "sample_forced_narrative",
    )
    assert build.returncode == 0, build.stderr
    built = parse_json_stdout(build)
    assert built["ok"] is True
    assert built["op"] == "forced_narrative_exact.build_report"
    report_json = Path(built["data"]["json_path"])
    assert report_json.is_file()
    assert Path(built["data"]["report_path"]).is_file()
    assert Path(built["data"]["csv_path"]).is_file()
    assert Path(built["data"]["srt_path"]).is_file()

    validate = run_script(
        SCRIPTS / "validate_report.py",
        "--report",
        str(report_json),
        "--input",
        str(sample_video),
    )
    assert validate.returncode == 0, validate.stderr
    validated = parse_json_stdout(validate)
    assert validated["ok"] is True
    assert validated["op"] == "forced_narrative_exact.validate_report"
