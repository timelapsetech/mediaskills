# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect overlapping black video + silent audio regions (TV break separators)."""

from __future__ import annotations

import argparse
import json

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_progress,
    emit_success,
    main_wrapper,
    probe_duration,
    require_cmd,
    resolve_output,
    validate_input_path,
)
from _segment_lib import (
    detect_blacks,
    detect_silences,
    intersect_black_silence,
    normalize_terminal_gap,
    probe_video_fps,
)

OP = "program_master.detect_black_silence"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect_black_silence.py --input program.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--noise", default="-30dB", help="Silence threshold (default -30dB)")
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum gap length in seconds (default 0.5)",
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
    parser.add_argument(
        "--min-overlap",
        type=float,
        default=0.25,
        help="Min seconds black and silence must overlap (default 0.25)",
    )
    parser.add_argument("--video-stream", type=int, default=0, help="Relative video stream index")
    parser.add_argument("--audio-stream", type=int, default=0, help="Relative audio stream index")
    parser.add_argument(
        "--audio-policy",
        choices=["single", "all"],
        default="single",
        help="Analyze one stream or require silence across all audio streams",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    noise = str(args.noise)
    min_duration = float(args.min_duration)
    pixel_threshold = float(args.pixel_threshold)
    picture_threshold = float(args.picture_threshold)
    min_overlap = float(args.min_overlap)

    emit_progress("detecting silence", 20)
    silences = detect_silences(
        str(path),
        noise=noise,
        min_duration=min_duration,
        audio_stream=int(args.audio_stream),
        audio_policy=str(args.audio_policy),
    )

    emit_progress("detecting blacks", 50)
    blacks = detect_blacks(
        str(path),
        min_duration=min_duration,
        pixel_threshold=pixel_threshold,
        picture_threshold=picture_threshold,
        refine_fades=bool(args.fade_refine),
        fade_handle_frames=max(0, int(args.fade_handle_frames)),
        video_stream=int(args.video_stream),
    )

    emit_progress("intersecting", 75)
    duration = probe_duration(str(path))
    gaps = intersect_black_silence(blacks, silences, min_overlap=min_overlap)
    normalize_terminal_gap(
        gaps,
        duration=duration,
        fps=probe_video_fps(str(path), video_stream=int(args.video_stream)),
    )

    out = resolve_output(str(path), "_black_silence.json", args.output)
    payload = {
        "input_path": str(path),
        "duration": duration,
        "black_silence_gaps": gaps,
        "silences": silences,
        "blacks": blacks,
        "black_detection": {
            "pixel_threshold": pixel_threshold,
            "picture_threshold": picture_threshold,
            "fade_refine": bool(args.fade_refine),
            "fade_handle_frames": max(0, int(args.fade_handle_frames)),
        },
        "gap_count": len(gaps),
        "selected_streams": {
            "video_stream": int(args.video_stream),
            "audio_stream": int(args.audio_stream),
            "audio_policy": str(args.audio_policy),
        },
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    emit_progress("done", 100)
    emit_success(OP, {**payload, "output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
