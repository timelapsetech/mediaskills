# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Flip an image horizontally or vertically using ImageMagick."""

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
        epilog="Example: uv run flip.py --input photo.png --direction horizontal",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--direction",
        choices=["horizontal", "vertical"],
        default="horizontal",
        help="Flip axis (default: horizontal)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.flip"
    path = validate_input_path(args.input, op)
    out = resolve_output(str(path), "_flip.png", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    require_cmd("convert", op)
    flag = "-flip" if args.direction == "vertical" else "-flop"
    run(["convert", str(path), flag, str(out)], op)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
