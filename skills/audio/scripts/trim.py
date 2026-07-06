# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Trim audio to a start/end time range."""

from __future__ import annotations

import argparse

from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_success,
    main_wrapper,
    parse_time_arg,
    require_cmd,
    resolve_output,
    run,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run trim.py --input track.wav --start 1.5 --end 5.0",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--start",
        required=True,
        help="Start time in seconds or HH:MM:SS[.mmm]",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End time in seconds or HH:MM:SS[.mmm]",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "audio.trim"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    start = parse_time_arg(args.start)
    end = parse_time_arg(args.end)
    if end <= start:
        emit_error(op, f"End ({end}) must be greater than start ({start})", code=EXIT_BAD_ARGS)
    out = resolve_output(str(path), "_trim.wav", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            str(path),
            "-c",
            "copy",
            str(out),
        ],
        op,
    )
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
