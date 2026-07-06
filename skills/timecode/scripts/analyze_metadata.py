# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Infer timecode format from ffprobe or MediaInfo-style metadata JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import EXIT_BAD_ARGS, emit_error, emit_success, main_wrapper
from _timecode_lib import analyze_metadata, build_timecode, timecode_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run analyze_metadata.py --input ffprobe.json",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="JSON file with ffprobe output, merged tags, or MediaInfo fields",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.analyze_metadata"
    path = Path(args.input)
    if not path.is_file():
        emit_error(op, f"File not found: {path}", code=EXIT_BAD_ARGS)

    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        emit_error(op, f"Invalid JSON: {exc}", code=EXIT_BAD_ARGS)

    if not isinstance(metadata, dict):
        emit_error(op, "Metadata root must be a JSON object", code=EXIT_BAD_ARGS)

    analysis = analyze_metadata(metadata)
    parsed = None
    if analysis.get("timecode") and analysis.get("fps"):
        ndf = analysis.get("inferred_drop_frame") is False
        tc = build_timecode(analysis["fps"], analysis["timecode"], force_non_drop_frame=ndf)
        parsed = timecode_payload(tc)

    emit_success(op, {**analysis, "parsed": parsed})


if __name__ == "__main__":
    main_wrapper(main)
