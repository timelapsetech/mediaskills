# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Extract embedded timecode metadata from a media file."""

from __future__ import annotations

import argparse

from _mediaskills_common import (
    add_input_arg,
    emit_success,
    ffprobe_json,
    main_wrapper,
    validate_input_path,
)
from _timecode_lib import analyze_metadata, build_timecode, timecode_from_seconds, timecode_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run extract.py --input clip.mov",
    )
    add_input_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "timecode.extract"
    path = validate_input_path(args.input, op)
    meta = ffprobe_json(str(path), op)
    analysis = analyze_metadata(meta)

    duration = float(meta.get("format", {}).get("duration") or 0)
    duration_tc = None
    if duration and analysis.get("fps"):
        duration_tc = timecode_payload(
            timecode_from_seconds(
                duration,
                analysis["fps"],
                force_non_drop_frame=analysis.get("inferred_drop_frame") is False,
            )
        )

    emit_success(
        op,
        {
            "input_path": str(path),
            "duration_seconds": duration,
            "duration_timecode": duration_tc,
            **analysis,
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
