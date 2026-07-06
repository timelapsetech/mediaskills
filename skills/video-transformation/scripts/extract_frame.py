# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract a single frame from video at a timestamp."""

from __future__ import annotations

import argparse
import subprocess

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_success,
    main_wrapper,
    parse_time_arg,
    probe_duration,
    require_cmd,
    resolve_output,
    run,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run extract_frame.py --input clip.mp4 --time 1.5",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--time",
        "--timestamp",
        dest="time",
        default="0",
        help="Timestamp in seconds or HH:MM:SS / MM:SS (default 0)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "video.extract_frame"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    require_cmd("ffprobe", op)

    try:
        duration = probe_duration(str(path))
    except (subprocess.CalledProcessError, ValueError):
        emit_error(op, f"Could not read duration for {path}")

    try:
        secs = parse_time_arg(str(args.time))
    except ValueError:
        secs = 0.0

    max_t = max(0.0, duration - 0.05)
    clamped = secs > max_t or secs < 0
    secs = min(max(secs, 0.0), max_t)

    safe_time = str(secs).replace(".", "_")
    if args.output:
        out = resolve_output(None, ".jpg", args.output)
    else:
        out = resolve_output(str(path), f"_frame_{safe_time}s.jpg", None)
    out.parent.mkdir(parents=True, exist_ok=True)

    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(secs),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-update",
            "1",
            "-q:v",
            "2",
            "-pix_fmt",
            "yuvj420p",
            str(out),
        ],
        op,
    )

    if not out.is_file() or out.stat().st_size == 0:
        emit_error(op, f"No frame written at {secs}s (video duration {duration}s)")

    emit_success(
        op,
        {
            "output_path": str(out),
            "time_seconds": secs,
            "duration_seconds": duration,
            "clamped": clamped,
        },
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
