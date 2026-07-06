# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Compare two media files."""

from __future__ import annotations

import argparse
from pathlib import Path

from _mediaskills_common import (
    compare_probe_summaries,
    emit_error,
    emit_success,
    ffprobe_json,
    main_wrapper,
    EXIT_BAD_ARGS,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-a", required=True, help="First media file")
    parser.add_argument("--input-b", required=True, help="Second media file")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "inspect.compare"
    a, b = Path(args.input_a), Path(args.input_b)
    if not a.is_file():
        emit_error(op, f"Input file not found: {a}", code=EXIT_BAD_ARGS)
    if not b.is_file():
        emit_error(op, f"Input file not found: {b}", code=EXIT_BAD_ARGS)
    probe_a = ffprobe_json(str(a), op)
    probe_b = ffprobe_json(str(b), op)
    emit_success(op, compare_probe_summaries(probe_a, probe_b))


if __name__ == "__main__":
    main_wrapper(main)
