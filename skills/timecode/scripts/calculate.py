# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Add or subtract an offset from SMPTE timecode."""

from __future__ import annotations

import argparse

from _mediaskills_common import EXIT_BAD_ARGS, emit_error, emit_success, main_wrapper
from _timecode_lib import build_timecode, timecode_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run calculate.py --timecode 01:00:00;00 --op add "
            "--offset-seconds 5 --fps 29.97"
        ),
    )
    parser.add_argument("--timecode", default="00:00:00:00", help="Base timecode")
    parser.add_argument("--fps", default="29.97", help="Frame rate")
    parser.add_argument("--op", choices=["add", "sub"], default="add", help="Add or subtract")
    parser.add_argument("--offset-seconds", type=float, help="Offset in seconds (wall clock)")
    parser.add_argument("--offset-timecode", help="Offset as SMPTE timecode")
    parser.add_argument(
        "--non-drop-frame",
        action="store_true",
        help="Force non-drop-frame interpretation",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.calculate"

    base = build_timecode(args.fps, args.timecode, force_non_drop_frame=args.non_drop_frame)

    if args.offset_timecode:
        offset_tc = build_timecode(
            args.fps,
            args.offset_timecode,
            force_non_drop_frame=args.non_drop_frame,
        )
        delta_frames = offset_tc.frame_number
    elif args.offset_seconds is not None:
        delta_frames = int(round(args.offset_seconds * base._int_framerate))
    else:
        emit_error(op, "Provide --offset-seconds or --offset-timecode", code=EXIT_BAD_ARGS)

    signed_frames = delta_frames if args.op == "add" else -delta_frames
    result = base + signed_frames
    emit_success(
        op,
        {
            "input_timecode": args.timecode,
            "op": args.op,
            "delta_frames": delta_frames,
            **timecode_payload(result),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
