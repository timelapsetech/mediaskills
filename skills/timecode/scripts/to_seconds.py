# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Convert SMPTE timecode to seconds and frame count."""

from __future__ import annotations

import argparse

from _mediaskills_common import EXIT_BAD_ARGS, emit_error, emit_success, main_wrapper
from _timecode_lib import build_timecode, timecode_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run to_seconds.py --timecode 00:01:00;00 --fps 29.97",
    )
    parser.add_argument("--timecode", required=True, help="SMPTE timecode HH:MM:SS:FF or HH:MM:SS;FF")
    parser.add_argument("--fps", default="29.97", help="Frame rate (default 29.97)")
    parser.add_argument(
        "--non-drop-frame",
        action="store_true",
        help="Force non-drop-frame interpretation at NTSC rates",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.to_seconds"
    if not args.timecode.strip():
        emit_error(op, "Missing timecode", code=EXIT_BAD_ARGS)

    tc = build_timecode(args.fps, args.timecode, force_non_drop_frame=args.non_drop_frame)
    payload = timecode_payload(tc)
    emit_success(
        op,
        {
            "input_timecode": args.timecode,
            **payload,
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
