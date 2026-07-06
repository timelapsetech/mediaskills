# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Legacy interval frame manifest (non-sequence layout)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_progress,
    emit_success,
    main_wrapper,
    probe_duration,
    require_cmd,
    resolve_output,
    run,
    validate_input_path,
)

OP = "vision.prepare_manifest"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run prepare_manifest.py --input clip.mp4 --interval 1",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between frames (default 1.0)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    interval = max(0.1, float(args.interval))
    duration = probe_duration(str(input_path))
    frames_dir = resolve_output(str(input_path), "_frames.dir").with_suffix("")
    frames_dir.mkdir(parents=True, exist_ok=True)

    emit_progress("extracting frames", 20)
    pattern = str(frames_dir / "frame_%06d.jpg")
    fps = 1.0 / interval
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"fps={fps}",
            "-q:v",
            "3",
            pattern,
        ],
        OP,
    )

    frames = []
    for i, path in enumerate(sorted(frames_dir.glob("frame_*.jpg"))):
        frames.append(
            {
                "index": i,
                "time_seconds": i * interval,
                "path": str(path),
            }
        )

    manifest = {
        "input_path": str(input_path.resolve()),
        "interval_seconds": interval,
        "duration_seconds": duration,
        "frames_dir": str(frames_dir),
        "frames": frames,
    }
    manifest_path = resolve_output(str(input_path), "_manifest.json", args.output)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    emit_progress("done", 100)
    emit_success(
        OP,
        {
            "manifest_path": str(manifest_path),
            "output_path": str(manifest_path),
            "frame_count": len(frames),
            "frames_dir": str(frames_dir),
            "frames": frames[:20],
        },
        [str(manifest_path)],
    )


if __name__ == "__main__":
    main_wrapper(main)
