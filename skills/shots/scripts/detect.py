# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect hard cuts (shot boundaries) via ffmpeg scene filter."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_progress,
    emit_success,
    main_wrapper,
    probe_duration,
    require_cmd,
    resolve_output,
    seconds_to_tc,
    validate_input_path,
)

OP = "shots.detect"


def probe_fps(path: str) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            text=True,
        ).strip()
        if "/" in out:
            num, den = out.split("/", 1)
            n, d = float(num), float(den)
            if d:
                return n / d
        return float(out)
    except Exception:
        return 29.97


def detect_cuts(input_path: str, threshold: float) -> list[tuple[float, float]]:
    """Return list of (pts_time, scene_score) for frames exceeding threshold."""
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            input_path,
            "-filter:v",
            f"select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    stderr = proc.stderr or ""
    cuts: list[tuple[float, float]] = []
    for line in stderr.splitlines():
        if "pts_time:" not in line:
            continue
        m_pts = re.search(r"pts_time:([0-9.]+)", line)
        if not m_pts:
            continue
        t = float(m_pts.group(1))
        m_score = re.search(r"lavfi\.scene_score=([0-9.]+)", line)
        score = float(m_score.group(1)) if m_score else threshold
        cuts.append((t, score))
    return cuts


def build_shots(
    duration: float,
    cuts: list[tuple[float, float]],
    fps: float,
    min_shot_seconds: float,
) -> list[dict]:
    boundaries = [0.0]
    scores_at: dict[float, float] = {}
    for t, score in cuts:
        if t <= 0.05 or t >= duration - 0.05:
            continue
        if boundaries and abs(boundaries[-1] - t) < 0.05:
            continue
        boundaries.append(t)
        scores_at[t] = score
    boundaries.append(duration)
    boundaries = sorted(set(boundaries))

    raw: list[dict] = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if end <= start:
            continue
        raw.append(
            {
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": end - start,
                "scene_score": scores_at.get(start),
            }
        )

    merged: list[dict] = []
    for shot in raw:
        if merged and shot["duration_seconds"] < min_shot_seconds:
            prev = merged[-1]
            prev["end_seconds"] = shot["end_seconds"]
            prev["duration_seconds"] = prev["end_seconds"] - prev["start_seconds"]
            continue
        if shot["duration_seconds"] < min_shot_seconds and not merged:
            merged.append(shot)
            continue
        merged.append(shot)

    if len(merged) >= 2 and merged[0]["duration_seconds"] < min_shot_seconds:
        nxt = merged[1]
        nxt["start_seconds"] = merged[0]["start_seconds"]
        nxt["duration_seconds"] = nxt["end_seconds"] - nxt["start_seconds"]
        merged = merged[1:]

    shots: list[dict] = []
    for i, shot in enumerate(merged):
        start = float(shot["start_seconds"])
        end = float(shot["end_seconds"])
        shots.append(
            {
                "index": i,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "duration_seconds": round(end - start, 3),
                "start_timecode": seconds_to_tc(start, fps),
                "end_timecode": seconds_to_tc(end, fps),
                "scene_score": shot.get("scene_score"),
            }
        )
    return shots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect.py --input clip.mp4 --threshold 0.35",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Scene-change score threshold 0–1 (default 0.35; lower finds more cuts)",
    )
    parser.add_argument(
        "--min-shot-seconds",
        type=float,
        default=0.5,
        help="Merge shots shorter than this into neighbors (default 0.5)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    threshold = max(0.01, min(1.0, float(args.threshold)))
    min_shot_seconds = max(0.0, float(args.min_shot_seconds))

    emit_progress("probing", 5)
    duration = probe_duration(str(path))
    fps = probe_fps(str(path))

    emit_progress("detecting cuts", 20)
    cuts = detect_cuts(str(path), threshold)

    emit_progress("building shots", 80)
    shots = build_shots(duration, cuts, fps, min_shot_seconds)

    manifest_path = resolve_output(str(path), "_shots.json", args.output)
    payload = {
        "input_path": str(path.resolve()),
        "duration_seconds": round(duration, 3),
        "fps": round(fps, 3),
        "threshold": threshold,
        "min_shot_seconds": min_shot_seconds,
        "shot_count": len(shots),
        "shots": shots,
        "frames": [],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    emit_progress("done", 100)
    emit_success(
        OP,
        {
            "manifest_path": str(manifest_path),
            "output_path": str(manifest_path),
            "shots_path": str(manifest_path),
            "shot_count": len(shots),
            "duration_seconds": round(duration, 3),
            "fps": round(fps, 3),
            "threshold": threshold,
            "shots": shots[:20],
        },
        [str(manifest_path)],
    )


if __name__ == "__main__":
    main_wrapper(main)
