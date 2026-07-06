# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Convert an image to another format using ImageMagick."""

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
        epilog="Example: uv run convert.py --input photo.jpg --format png",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--format",
        "-f",
        default="png",
        help="Output format extension without dot (default: png)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.convert"
    path = validate_input_path(args.input, op)
    fmt = args.format.lstrip(".")
    out = resolve_output(str(path), f".{fmt}", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    require_cmd("convert", op)
    run(["convert", str(path), str(out)], op)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
