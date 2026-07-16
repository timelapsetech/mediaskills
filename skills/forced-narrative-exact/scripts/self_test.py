# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Self-contained golden test for forced-narrative build + validate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import emit
from _mediaskills_common import main_wrapper, require_cmd

OP = "forced_narrative_exact.self_test"
SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"
REPO_ROOT = SKILL_DIR.parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        help="Optional directory to retain the synthetic refined JSON and report outputs",
    )
    return parser


def probe_fps(path: Path) -> str:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return (result.stdout.strip() or "30/1").splitlines()[0]


def run_script(*args: str) -> dict:
    if shutil.which("uv"):
        cmd = ["uv", "run", *args]
    else:
        cmd = [sys.executable, *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"exit {proc.returncode}")
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


def main() -> None:
    args = build_parser().parse_args()
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    source = FIXTURES / "burned_in_captions.mp4"
    meta_path = FIXTURES / "burned_in_captions.meta.json"
    if not source.is_file() or not meta_path.is_file():
        gen = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "generate_fixtures.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if gen.returncode != 0 or not source.is_file():
            emit(
                False,
                OP,
                {"error": f"missing fixture {source}; generate_fixtures failed: {gen.stderr}"},
            )
            raise SystemExit(3)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    work = Path(args.work_dir).expanduser().resolve() if args.work_dir else Path(tempfile.mkdtemp())
    work.mkdir(parents=True, exist_ok=True)
    os.environ["MEDIASKILLS_DATA_DIR"] = str(work)
    reports = work / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    # Known cue covering the visible overlay window (~frames 15..60 at 30fps)
    fps = probe_fps(source)
    refined = {
        "schema_version": "1.0",
        "input_path": str(source.resolve()),
        "fps": fps,
        "drop_frame": False,
        "embedded_start_timecode": None,
        "crop": meta["caption_band"],
        "rows": [
            {
                "id": 1,
                "start_frame": 15,
                "end_frame_exclusive": 60,
                "speaker_context": "",
                "lines": ["HELLO WORLD"],
                "text": "HELLO WORLD",
            }
        ],
    }
    refined_path = work / "refined.json"
    refined_path.write_text(json.dumps(refined, indent=2) + "\n", encoding="utf-8")

    built = run_script(
        str(SCRIPTS / "build_report.py"),
        "--refined",
        str(refined_path),
        "--output-dir",
        str(reports),
        "--stem",
        "burned_in_self_test",
    )
    if not built.get("ok"):
        raise RuntimeError(built)
    report_json = Path(built["data"]["json_path"])
    for key in ("report_path", "json_path", "csv_path", "srt_path"):
        path = Path(built["data"][key])
        if not path.is_file() or path.stat().st_size < 1:
            raise RuntimeError(f"missing deliverable {key}: {path}")

    report = json.loads(report_json.read_text(encoding="utf-8"))
    rows = report.get("rows") or []
    if len(rows) != 1:
        raise RuntimeError(f"expected 1 cue, got {len(rows)}")
    text = str(rows[0].get("text") or "")
    needle = str(meta["expected_text_contains"])
    if needle not in text.upper():
        raise RuntimeError(f"cue text {text!r} missing {needle!r}")

    validated = run_script(
        str(SCRIPTS / "validate_report.py"),
        "--report",
        str(report_json),
        "--input",
        str(source),
    )
    if not validated.get("ok"):
        raise RuntimeError(validated)

    ocr_note = "skipped (tesseract not on PATH)"
    if shutil.which("tesseract"):
        scanned = run_script(
            str(SCRIPTS / "scan_caption_band.py"),
            "--input",
            str(source),
            "--interval",
            "0.5",
            "--force",
        )
        if not scanned.get("ok"):
            raise RuntimeError(scanned)
        ocr_note = f"scan_caption_band ok → {scanned['data'].get('output_path')}"

    emit(
        True,
        OP,
        {
            "source": str(source),
            "work_dir": str(work),
            "report_json": str(report_json),
            "cue_count": 1,
            "ocr": ocr_note,
            "validated": True,
        },
        [str(report_json), str(built["data"]["report_path"])],
    )


if __name__ == "__main__":
    main_wrapper(main)
