# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract text from an image using Tesseract OCR."""

from __future__ import annotations

import argparse
import subprocess

from _mediaskills_common import (
    add_input_arg,
    emit_success,
    main_wrapper,
    require_cmd,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run ocr.py --input scan.png",
    )
    add_input_arg(parser)
    parser.add_argument(
        "--lang",
        default="eng",
        help="Tesseract language code (default: eng)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "image.ocr"
    path = validate_input_path(args.input, op)
    require_cmd("tesseract", op)
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", args.lang],
        capture_output=True,
        text=True,
    )
    text = result.stdout if result.returncode == 0 else ""
    emit_success(op, {"text": text})


if __name__ == "__main__":
    main_wrapper(main)
