# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Probe a media file with ffprobe and return structured metadata."""

from __future__ import annotations

import argparse
import json

from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_input_arg,
    emit_error,
    emit_success,
    ffprobe_json,
    main_wrapper,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run probe.py --input video.mp4",
    )
    add_input_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "inspect.probe"
    path = validate_input_path(args.input, op)
    data = ffprobe_json(str(path), op)
    emit_success(op, data)


if __name__ == "__main__":
    main_wrapper(main)
