# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect black video regions via ffmpeg blackdetect."""

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
from _segment_lib import detect_blacks

OP = "program_master.detect_blacks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect_blacks.py --input program.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum black region length in seconds (default 0.5)",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=float,
        default=0.01,
        help="Per-pixel black luma threshold; lower is stricter (default 0.01)",
    )
    parser.add_argument(
        "--picture-threshold",
        type=float,
        default=0.98,
        help="Fraction of pixels that must be black (default 0.98)",
    )
    parser.add_argument(
        "--fade-refine",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Refine gradual black transitions to mathematical anchor frames (default on)",
    )
    parser.add_argument(
        "--fade-handle-frames",
        type=int,
        default=1,
        help="Black anchor frames assigned to detected fades (default 1)",
    )
    parser.add_argument("--video-stream", type=int, default=0, help="Relative video stream index")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    emit_progress("detecting blacks", 50)
    segments = detect_blacks(
        str(path),
        min_duration=float(args.min_duration),
        pixel_threshold=float(args.pixel_threshold),
        picture_threshold=float(args.picture_threshold),
        refine_fades=bool(args.fade_refine),
        fade_handle_frames=max(0, int(args.fade_handle_frames)),
        video_stream=int(args.video_stream),
    )

    out = resolve_output(str(path), "_blacks.json", args.output)
    payload = {
        "input_path": str(path),
        "segments": segments,
        "blacks": segments,
        "black_detection": {
            "pixel_threshold": float(args.pixel_threshold),
            "picture_threshold": float(args.picture_threshold),
            "fade_refine": bool(args.fade_refine),
            "fade_handle_frames": max(0, int(args.fade_handle_frames)),
        },
        "count": len(segments),
        "video_stream": int(args.video_stream),
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
