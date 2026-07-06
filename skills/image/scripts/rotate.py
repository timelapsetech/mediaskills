# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Rotate an image using ImageMagick."""

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
        epilog="Example: uv run rotate.py --input photo.png --degrees 90",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--degrees",
        "-d",
        type=float,
        default=90.0,
        help="Clockwise rotation in degrees (default: 90)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.rotate"
    path = validate_input_path(args.input, op)
    out = resolve_output(str(path), "_rot.png", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    require_cmd("convert", op)
    run(["convert", str(path), "-rotate", str(args.degrees), str(out)], op)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
