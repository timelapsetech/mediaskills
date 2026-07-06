# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Convert SMPTE timecode between frame rates."""

from __future__ import annotations

import argparse

from _mediaskills_common import EXIT_BAD_ARGS, emit_error, emit_success, main_wrapper
from timecode import Timecode

from _timecode_lib import (
    build_timecode,
    convert_realtime,
    normalize_fps,
    timecode_payload,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run convert.py --timecode 00:01:00:00 --from-fps 24 --to-fps 29.97",
    )
    parser.add_argument("--timecode", required=True, help="Input timecode")
    parser.add_argument("--from-fps", default="29.97", help="Source frame rate")
    parser.add_argument("--to-fps", help="Target frame rate (default: same as from-fps)")
    parser.add_argument(
        "--non-drop-frame",
        action="store_true",
        help="Force non-drop-frame interpretation on input",
    )
    parser.add_argument(
        "--target-non-drop-frame",
        action="store_true",
        help="Force non-drop-frame on output at NTSC rates",
    )
    parser.add_argument(
        "--preserve",
        choices=["realtime", "frames"],
        default="realtime",
        help="Preserve wall-clock duration (realtime) or frame index (frames)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.convert"
    if not args.timecode.strip():
        emit_error(op, "Missing timecode", code=EXIT_BAD_ARGS)

    from_fps = args.from_fps
    to_fps = args.to_fps if args.to_fps is not None else from_fps
    source = build_timecode(from_fps, args.timecode, force_non_drop_frame=args.non_drop_frame)

    target_ndf = args.target_non_drop_frame or source.force_non_drop_frame
    if args.preserve == "frames":
        target = Timecode(
            normalize_fps(to_fps),
            frames=source.frames,
            force_non_drop_frame=target_ndf,
        )
    else:
        target = convert_realtime(source, to_fps, force_non_drop_frame=target_ndf)

    emit_success(
        op,
        {
            "input_timecode": args.timecode,
            "from_fps": from_fps,
            "to_fps": to_fps,
            "preserve": args.preserve,
            **timecode_payload(target),
            "source": timecode_payload(source),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
