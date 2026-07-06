# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Convert seconds to SMPTE timecode."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_success, main_wrapper
from _timecode_lib import build_timecode, timecode_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run from_seconds.py --seconds 60 --fps 29.97 --drop-frame",
    )
    parser.add_argument("--seconds", type=float, required=True, help="Elapsed seconds (wall clock)")
    parser.add_argument("--fps", default="29.97", help="Frame rate (default 29.97)")
    parser.add_argument(
        "--drop-frame",
        action="store_true",
        help="Emit drop-frame timecode at NTSC rates (default for 29.97/59.94)",
    )
    parser.add_argument(
        "--non-drop-frame",
        action="store_true",
        help="Force non-drop-frame timecode at NTSC rates",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.from_seconds"
    tc = build_timecode(
        args.fps,
        seconds=args.seconds,
        force_non_drop_frame=args.non_drop_frame,
    )
    emit_success(
        op,
        {
            "input_seconds": args.seconds,
            **timecode_payload(tc),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
