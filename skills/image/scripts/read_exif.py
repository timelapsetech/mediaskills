# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Read EXIF and other metadata from an image using exiftool."""

from __future__ import annotations

import argparse
import json

from _mediaskills_common import (
    add_input_arg,
    emit_success,
    main_wrapper,
    require_cmd,
    run,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run read_exif.py --input photo.jpg",
    )
    add_input_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.read_exif"
    path = validate_input_path(args.input, op)
    require_cmd("exiftool", op)
    result = run(["exiftool", "-json", str(path)], op)
    data = json.loads(result.stdout)
    emit_success(op, data)


if __name__ == "__main__":
    main_wrapper(main)
