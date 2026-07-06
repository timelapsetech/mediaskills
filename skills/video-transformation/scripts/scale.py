# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Scale video resolution."""

from __future__ import annotations

import argparse

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_success,
    main_wrapper,
    require_cmd,
    resolve_output,
    run,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run scale.py --input clip.mp4 --width 1280 --height 720",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--width", type=int, required=True, help="Output width in pixels")
    parser.add_argument(
        "--height",
        type=int,
        default=-2,
        help="Output height (-2 keeps aspect, default -2)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "video.scale"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    out = resolve_output(str(path), "_scale.mp4", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-vf",
            f"scale={args.width}:{args.height}",
            "-c:a",
            "copy",
            str(out),
        ],
        op,
    )
    emit_success(op, {"output_path": str(out), "width": args.width, "height": args.height}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
