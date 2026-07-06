# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect on-screen text in a video via frame sampling + tesseract OCR."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    emit_error,
    emit_progress,
    emit_success,
    generated_dir,
    main_wrapper,
    probe_duration,
    require_cmd,
    run,
    validate_input_path,
)

OP = "vision.compile_report"


def format_tc(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def is_strong_line(line: str) -> bool:
    if re.search(r"\b\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\b", line):
        return True
    letters = sum(ch.isalpha() for ch in line)
    if letters < 6:
        return False
    if letters / max(len(line), 1) < 0.55:
        return False
    words = re.findall(r"[A-Za-z]{4,}", line)
    return len(words) >= 2 or (len(words) == 1 and len(words[0]) >= 6)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and is_strong_line(ln)]
    return "\n".join(lines)


def texts_similar(a: str, b: str) -> bool:
    na = re.sub(r"\s+", " ", a).strip().lower()
    nb = re.sub(r"\s+", " ", b).strip().lower()
    if not na and not nb:
        return True
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return False


def ocr_frame(image_path: Path) -> str:
    try:
        out = subprocess.check_output(
            ["tesseract", str(image_path), "stdout", "--psm", "6"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except subprocess.CalledProcessError:
        return ""
    return normalize_text(out)


def extract_frames(input_path: str, out_dir: Path, interval: float) -> list[tuple[float, Path]]:
    pattern = str(out_dir / "frame_%06d.jpg")
    fps = 1.0 / max(interval, 0.1)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            input_path,
            "-vf",
            f"fps={fps}",
            "-q:v",
            "3",
            pattern,
        ],
        OP,
    )
    frames = sorted(out_dir.glob("frame_*.jpg"))
    return [(i * interval, path) for i, path in enumerate(frames)]


def merge_detections(samples: list[tuple[float, str]], interval: float) -> list[dict]:
    rows: list[dict] = []
    for t, text in samples:
        if not text or not text.strip():
            continue
        if rows and texts_similar(rows[-1]["text"], text):
            rows[-1]["end_seconds"] = t + interval
            rows[-1]["end_timecode"] = format_tc(t + interval)
            if len(text) > len(rows[-1]["text"]):
                rows[-1]["text"] = text
        else:
            rows.append(
                {
                    "start_seconds": t,
                    "end_seconds": t + interval,
                    "start_timecode": format_tc(t),
                    "end_timecode": format_tc(t + interval),
                    "text": text,
                }
            )
    return rows


def write_reports(stem: str, rows: list[dict], meta: dict) -> list[Path]:
    out_dir = generated_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"{ts}_{random.randint(1000, 9999)}"
    json_path = out_dir / f"{stem}_onscreen_text_{suffix}.json"
    md_path = out_dir / f"{stem}_onscreen_text_{suffix}.md"
    csv_path = out_dir / f"{stem}_onscreen_text_{suffix}.csv"

    payload = {**meta, "rows": rows}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# On-screen text report: {meta.get('input_name', stem)}",
        "",
        f"- Source: `{meta.get('input_path')}`",
        f"- Duration: {meta.get('duration_seconds')}s",
        f"- Sample interval: {meta.get('interval_seconds')}s",
        f"- Detections: {len(rows)}",
        "",
        "| Start Timecode | End Timecode | Text |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        text = row["text"].replace("|", "\\|").replace("\n", "<br>")
        lines.append(f"| {row['start_timecode']} | {row['end_timecode']} | {text} |")
    if not rows:
        lines.append("| — | — | _No on-screen text detected_ |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["start_timecode", "end_timecode", "start_seconds", "end_seconds", "text"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return [md_path, json_path, csv_path]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run compile_report.py --input clip.mp4",
    )
    add_input_arg(parser)
    parser.add_argument(
        "--interval",
        type=float,
        help="Seconds between OCR samples (default: auto ~180 samples across duration)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    video = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    try:
        subprocess.run(["tesseract", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        emit_error(OP, "tesseract not found. Install tesseract OCR.", code=2)

    emit_progress("probing", 5)
    duration = probe_duration(str(video))
    if args.interval is None:
        interval = max(1.0, duration / 180.0)
    else:
        interval = float(args.interval)
    interval = max(0.5, interval)

    with tempfile.TemporaryDirectory() as tmp:
        frame_dir = Path(tmp) / "frames"
        frame_dir.mkdir()
        emit_progress("extracting frames", 15)
        frames = extract_frames(str(video), frame_dir, interval)
        if not frames:
            emit_error(OP, "No frames extracted from video")

        samples: list[tuple[float, str]] = []
        total = len(frames)
        for i, (t, frame_path) in enumerate(frames):
            text = ocr_frame(frame_path)
            samples.append((t, text))
            emit_progress("ocr", 20 + 70 * (i + 1) / total)

        rows = merge_detections(samples, interval)
        emit_progress("writing report", 95)
        outputs = write_reports(
            video.stem,
            rows,
            {
                "input_path": str(video.resolve()),
                "input_name": video.name,
                "duration_seconds": round(duration, 3),
                "interval_seconds": round(interval, 3),
                "frame_count": total,
                "detection_count": len(rows),
            },
        )

    emit_progress("done", 100)
    emit_success(
        OP,
        {
            "input_path": str(video.resolve()),
            "output_path": str(outputs[0]),
            "report_path": str(outputs[0]),
            "json_path": str(outputs[1]),
            "csv_path": str(outputs[2]),
            "rows": rows,
            "row_count": len(rows),
            "interval_seconds": round(interval, 3),
            "duration_seconds": round(duration, 3),
        },
        [str(p) for p in outputs],
    )


if __name__ == "__main__":
    main_wrapper(main)
