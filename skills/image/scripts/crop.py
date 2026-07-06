# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Crop a region from an image using ImageMagick."""

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
        epilog="Example: uv run crop.py --input photo.png --width 100 --height 80 --x 10 --y 5",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--width", "-W", type=int, required=True, help="Crop width in pixels")
    parser.add_argument("--height", "-H", type=int, required=True, help="Crop height in pixels")
    parser.add_argument("--x", type=int, default=0, help="Left offset (default: 0)")
    parser.add_argument("--y", type=int, default=0, help="Top offset (default: 0)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.crop"
    path = validate_input_path(args.input, op)
    out = resolve_output(str(path), "_crop.png", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    geometry = f"{args.width}x{args.height}+{args.x}+{args.y}"
    require_cmd("convert", op)
    run(["convert", str(path), "-crop", geometry, str(out)], op)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
