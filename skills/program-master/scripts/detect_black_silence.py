# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect overlapping black video + silent audio regions (TV break separators)."""

from __future__ import annotations

import argparse
import json

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_progress,
    emit_success,
    main_wrapper,
    probe_duration,
    require_cmd,
    resolve_output,
    validate_input_path,
)
from _segment_lib import detect_blacks, detect_silences, intersect_black_silence

OP = "program_master.detect_black_silence"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect_black_silence.py --input program.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--noise", default="-30dB", help="Silence threshold (default -30dB)")
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum gap length in seconds (default 0.5)",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=float,
        default=0.10,
        help="Black pixel ratio threshold (default 0.10)",
    )
    parser.add_argument(
        "--min-overlap",
        type=float,
        default=0.25,
        help="Min seconds black and silence must overlap (default 0.25)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)

    noise = str(args.noise)
    min_duration = float(args.min_duration)
    pixel_threshold = float(args.pixel_threshold)
    min_overlap = float(args.min_overlap)

    emit_progress("detecting silence", 20)
    silences = detect_silences(str(path), noise=noise, min_duration=min_duration)

    emit_progress("detecting blacks", 50)
    blacks = detect_blacks(
        str(path),
        min_duration=min_duration,
        pixel_threshold=pixel_threshold,
    )

    emit_progress("intersecting", 75)
    gaps = intersect_black_silence(blacks, silences, min_overlap=min_overlap)
    duration = probe_duration(str(path))

    out = resolve_output(str(path), "_black_silence.json", args.output)
    payload = {
        "input_path": str(path),
        "duration": duration,
        "black_silence_gaps": gaps,
        "silences": silences,
        "blacks": blacks,
        "gap_count": len(gaps),
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    emit_progress("done", 100)
    emit_success(OP, {**payload, "output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
