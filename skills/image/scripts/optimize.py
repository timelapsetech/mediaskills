# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Optimize image file size (strip metadata, JPEG quality 85)."""

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
        epilog="Example: uv run optimize.py --input photo.png",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.optimize"
    path = validate_input_path(args.input, op)
    out = resolve_output(str(path), "_opt.jpg", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    require_cmd("convert", op)
    run(["convert", str(path), "-strip", "-quality", "85", str(out)], op)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
