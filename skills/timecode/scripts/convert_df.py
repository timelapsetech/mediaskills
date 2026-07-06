# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Convert between drop-frame and non-drop-frame timecode display."""

from __future__ import annotations

import argparse

from _mediaskills_common import EXIT_BAD_ARGS, emit_error, emit_success, main_wrapper
from _timecode_lib import build_timecode, convert_drop_frame_mode, timecode_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run convert_df.py --timecode 01:00:00;00 --fps 29.97 "
            "--to non-drop-frame"
        ),
    )
    parser.add_argument("--timecode", required=True, help="Input timecode")
    parser.add_argument("--fps", default="29.97", help="Frame rate")
    parser.add_argument(
        "--to",
        dest="target_mode",
        choices=["drop-frame", "non-drop-frame"],
        required=True,
        help="Target drop-frame mode",
    )
    parser.add_argument(
        "--preserve",
        choices=["realtime", "frames"],
        default="realtime",
        help="Match wall-clock (realtime) or keep the same frame index (frames)",
    )
    parser.add_argument(
        "--non-drop-frame",
        action="store_true",
        help="Interpret input as non-drop-frame (only if string uses colons)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.convert_df"
    if not args.timecode.strip():
        emit_error(op, "Missing timecode", code=EXIT_BAD_ARGS)

    source = build_timecode(args.fps, args.timecode, force_non_drop_frame=args.non_drop_frame)
    to_df = args.target_mode == "drop-frame"
    target = convert_drop_frame_mode(source, to_drop_frame=to_df, preserve=args.preserve)

    emit_success(
        op,
        {
            "input_timecode": args.timecode,
            "target_mode": args.target_mode,
            "preserve": args.preserve,
            **timecode_payload(target),
            "source": timecode_payload(source),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
