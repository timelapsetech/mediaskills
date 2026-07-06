# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Legacy silence-based program structure analysis without labeling."""

from __future__ import annotations

import argparse
import json
import re
import subprocess

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

OP = "program_master.analyze_structure"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run analyze_structure.py --input program.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--noise", default="-30dB", help="Silence threshold (default -30dB)")
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum silence length in seconds (default 0.5)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=29.97,
        help="Timecode display fps (default 29.97)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    duration = probe_duration(str(path))
    noise = str(args.noise)
    min_d = float(args.min_duration)
    fps = float(args.fps)

    emit_progress("detecting silence", 20)
    sil_proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise}:d={min_d}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    sil_text = sil_proc.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", sil_text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", sil_text)]
    silences = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else min(duration, s + min_d)
        silences.append({"start": s, "end": e, "duration": max(0.0, e - s)})

    emit_progress("detecting blacks", 50)
    blk_proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            f"blackdetect=d={min_d}:pix_th=0.10",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    blacks = []
    for m in re.finditer(
        r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)",
        blk_proc.stderr or "",
    ):
        blacks.append(
            {
                "start": float(m.group(1)),
                "end": float(m.group(2)),
                "duration": float(m.group(3)),
            }
        )

    cuts = sorted({0.0, duration, *[s["start"] for s in silences], *[s["end"] for s in silences]})
    segments = []
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        if b - a < 0.25:
            continue
        if any(abs(s["start"] - a) < 0.05 and abs(s["end"] - b) < 0.05 for s in silences):
            continue
        segments.append(
            {
                "index": len(segments),
                "start": a,
                "end": b,
                "duration": b - a,
                "start_timecode": seconds_to_tc(a, fps),
                "end_timecode": seconds_to_tc(b, fps),
            }
        )

    out = resolve_output(str(path), "_structure.json", args.output)
    payload = {
        "input_path": str(path),
        "duration": duration,
        "segments": segments,
        "silences": silences,
        "blacks": blacks,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    emit_progress("done", 100)
    emit_success(OP, {**payload, "output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
