# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Get duration of a media file in seconds."""

from __future__ import annotations

import argparse

from _mediaskills_common import (
    add_input_arg,
    emit_success,
    main_wrapper,
    probe_duration,
    require_cmd,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_input_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "inspect.duration"
    path = validate_input_path(args.input, op)
    require_cmd("ffprobe", op)
    duration = probe_duration(str(path))
    emit_success(op, {"duration_seconds": duration})


if __name__ == "__main__":
    main_wrapper(main)
