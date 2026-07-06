# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect silent audio regions via ffmpeg silencedetect."""

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
from _segment_lib import detect_silences

OP = "program_master.detect_silence"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect_silence.py --input program.mp4 --noise -30dB",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--noise",
        default="-30dB",
        help="Silence threshold for silencedetect (default -30dB)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum silence length in seconds (default 0.5)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)

    emit_progress("detecting silence", 50)
    segments = detect_silences(
        str(path),
        noise=str(args.noise),
        min_duration=float(args.min_duration),
    )

    out = resolve_output(str(path), "_silences.json", args.output)
    payload = {
        "input_path": str(path),
        "segments": segments,
        "silences": segments,
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
