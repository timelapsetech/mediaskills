# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Infer drop-frame vs non-drop-frame from a timecode string and optional fps."""

from __future__ import annotations

import argparse

from _mediaskills_common import EXIT_BAD_ARGS, emit_error, emit_success, main_wrapper
from _timecode_lib import analyze_timecode_string, build_timecode, timecode_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect_format.py --timecode 01:00:00;00 --fps 29.97",
    )
    parser.add_argument("--timecode", required=True, help="Timecode string to analyze")
    parser.add_argument("--fps", help="Nominal frame rate (helps NTSC inference)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.detect_format"
    if not args.timecode.strip():
        emit_error(op, "Missing timecode", code=EXIT_BAD_ARGS)

    analysis = analyze_timecode_string(args.timecode, args.fps)
    parsed = None
    if args.fps:
        ndf = analysis["inferred_drop_frame"] is False
        tc = build_timecode(args.fps, args.timecode, force_non_drop_frame=ndf)
        parsed = timecode_payload(tc)

    emit_success(op, {**analysis, "parsed": parsed})


if __name__ == "__main__":
    main_wrapper(main)
