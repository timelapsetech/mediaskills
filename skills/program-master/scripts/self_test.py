# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf==6.14.2", "reportlab==5.0.0", "timecode==1.5.1"]
# ///

"""Run a self-contained golden test of detection, timecode, thumbnails, PDF, and QC."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

from _mediaskills_common import emit_error, emit_success, main_wrapper, require_cmd
from _provenance_lib import sha256_file

OP = "program_master.self_test"
SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = SKILL_DIR / "profiles" / "broadcast-default.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        help="Optional directory in which to retain the synthetic source and both report bundles",
    )
    return parser


def synthesize_master(path: Path) -> None:
    video_inputs = [
        "color=c=red:s=320x180:r=24:d=2",
        "color=c=black:s=320x180:r=24:d=1",
        "testsrc2=s=320x180:r=24:d=3",
        "color=c=black:s=320x180:r=24:d=1",
        "color=c=green:s=320x180:r=24:d=2",
        "color=c=black:s=320x180:r=24:d=1",
    ]
    audio_inputs = [
        "sine=frequency=440:sample_rate=48000:duration=2",
        "anullsrc=r=48000:cl=mono:d=1",
        "sine=frequency=660:sample_rate=48000:duration=3",
        "anullsrc=r=48000:cl=mono:d=1",
        "sine=frequency=880:sample_rate=48000:duration=2",
        "anullsrc=r=48000:cl=mono:d=1",
    ]
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for source in video_inputs:
        command.extend(["-f", "lavfi", "-i", source])
    for source in audio_inputs:
        command.extend(["-f", "lavfi", "-i", source])
    command.extend(
        [
            "-filter_complex",
            (
                "[0:v]format=yuv420p[v0];"
                "[1:v]format=yuv420p[v1];"
                "[2:v]format=yuv420p,fade=t=in:st=0:d=0.8[v2];"
                "[3:v]format=yuv420p[v3];"
                "[4:v]format=yuv420p[v4];"
                "[5:v]format=yuv420p[v5];"
                "[v0][v1][v2][v3][v4][v5]concat=n=6:v=1:a=0[v];"
                "[6:a][7:a][8:a][9:a][10:a][11:a]concat=n=6:v=0:a=1[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "mpeg4",
            "-q:v",
            "2",
            "-c:a",
            "pcm_s16le",
            "-timecode",
            "01:00:00:00",
            "-metadata:s:v:0",
            "timecode=01:00:00:00",
            str(path),
        ]
    )
    subprocess.run(command, check=True, capture_output=True, text=True)


def run_bundle(source: Path, output_dir: Path, profile: Path) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts" / "run_report.py"),
            "--input",
            str(source),
            "--output-dir",
            str(output_dir),
            "--profile",
            str(profile),
            "--ocr-mode",
            "off",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "run_report failed").strip())
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    result = json.loads(lines[-1])
    if not result.get("ok"):
        raise RuntimeError(str(result))
    return result["data"]


def verify_bundle(result: dict) -> dict:
    artifacts = result["artifacts"]
    manifest = json.loads(Path(artifacts["manifest"]).read_text(encoding="utf-8"))
    thumbnail_report = json.loads(
        Path(artifacts["thumbnail_report_json"]).read_text(encoding="utf-8")
    )
    qc = json.loads(Path(artifacts["qc"]).read_text(encoding="utf-8"))
    segments = manifest["segments"]
    types = [segment["segment_type"] for segment in segments]
    expected_types = ["content", "gap", "content", "gap", "content", "gap"]
    if types != expected_types:
        raise RuntimeError(f"unexpected synthetic segment structure: {types}")
    if segments[0]["start_timecode"] != "01:00:00:00":
        raise RuntimeError("embedded start timecode was not preserved")
    if not manifest["validation"]["passed"] or not qc["passed"]:
        raise RuntimeError("manifest or final bundle QC failed")

    rows = thumbnail_report["rows"]
    faded = rows[2]
    thumbnail = faded.get("thumbnail") or {}
    if int(thumbnail.get("source_frame", -1)) <= int(faded["start_frame"]):
        raise RuntimeError("fade-up thumbnail did not advance past the black start frame")
    pdf_path = Path(artifacts["pdf"])
    pages = len(PdfReader(str(pdf_path)).pages)
    if pages < 1:
        raise RuntimeError("golden PDF contains no pages")
    return {
        "segment_types": types,
        "first_timecode": segments[0]["start_timecode"],
        "fade_thumbnail_offset_frames": thumbnail["offset_frames_from_segment_start"],
        "pdf_pages": pages,
        "pdf_sha256": sha256_file(pdf_path),
        "source_sha256": manifest["provenance"]["source"]["sha256"],
    }


def execute(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "program_master_golden.mov"
    profile_path = root / "golden-profile.json"
    synthesize_master(source)
    profile = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
    profile["name"] = "golden-self-test"
    profile["detection"].update({"min_duration": 0.4, "min_overlap": 0.2})
    profile["timecode"]["require_embedded"] = True
    profile["ocr"]["mode"] = "off"
    profile["validation"]["min_gaps"] = 3
    profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

    first = verify_bundle(run_bundle(source, root / "run_a", profile_path))
    second = verify_bundle(run_bundle(source, root / "run_b", profile_path))
    if first["pdf_sha256"] != second["pdf_sha256"]:
        raise RuntimeError("deterministic PDF hashes differed across identical runs")
    if first["source_sha256"] != second["source_sha256"]:
        raise RuntimeError("source provenance hashes differed across identical runs")
    return {"passed": True, "work_dir": str(root), "golden": first}


def main() -> None:
    args = build_parser().parse_args()
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)
    if args.work_dir:
        root = Path(args.work_dir).expanduser().resolve()
        result = execute(root)
        outputs = [str(root)]
    else:
        temp = Path(tempfile.mkdtemp(prefix="program-master-self-test-"))
        try:
            result = execute(temp)
            result["work_dir"] = None
            outputs = []
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    emit_success(OP, result, outputs)


if __name__ == "__main__":
    main_wrapper(main)
