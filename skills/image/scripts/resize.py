# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Resize an image using ImageMagick."""

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
        epilog="Example: uv run resize.py --input photo.png --width 800 --height 600",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--width", "-W", type=int, required=True, help="Target width in pixels")
    parser.add_argument(
        "--height",
        "-H",
        type=int,
        default=None,
        help="Target height in pixels (optional; preserves aspect if omitted)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.resize"
    path = validate_input_path(args.input, op)
    out = resolve_output(str(path), "_resize.png", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    size = f"{args.width}x{args.height or ''}"
    require_cmd("convert", op)
    run(["convert", str(path), "-resize", size, str(out)], op)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
