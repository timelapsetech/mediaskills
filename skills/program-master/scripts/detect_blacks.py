# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect black video regions via ffmpeg blackdetect."""

from __future__ import annotations

import argparse
import json

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_progress,
    emit_success,
    main_wrapper,
    require_cmd,
    resolve_output,
    validate_input_path,
)
from _segment_lib import detect_blacks

OP = "program_master.detect_blacks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect_blacks.py --input program.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum black region length in seconds (default 0.5)",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=float,
        default=0.10,
        help="Black pixel ratio threshold for blackdetect (default 0.10)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)

    emit_progress("detecting blacks", 50)
    segments = detect_blacks(
        str(path),
        min_duration=float(args.min_duration),
        pixel_threshold=float(args.pixel_threshold),
    )

    out = resolve_output(str(path), "_blacks.json", args.output)
    payload = {
        "input_path": str(path),
        "segments": segments,
        "blacks": segments,
        "count": len(segments),
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    emit_progress("done", 100)
    emit_success(
        OP,
        {**payload, "output_path": str(out)},
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
