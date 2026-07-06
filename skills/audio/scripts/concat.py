# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Concatenate multiple audio files into one."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_output_arg,
    emit_error,
    emit_success,
    main_wrapper,
    require_cmd,
    resolve_output,
    run,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run concat.py --paths part1.wav part2.wav --output joined.wav",
    )
    add_output_arg(parser)
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="Input audio files to concatenate (in order)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "audio.concat"
    require_cmd("ffmpeg", op)
    paths: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if not path.is_file():
            emit_error(op, f"Input file not found: {p}", code=EXIT_BAD_ARGS)
        paths.append(path)
    if len(paths) < 1:
        emit_error(op, "At least one input path is required", code=EXIT_BAD_ARGS)
    out = resolve_output(str(paths[0]), "_concat.mp3", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        list_path = Path(f.name)
        for path in paths:
            escaped = str(path).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    try:
        run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(out),
            ],
            op,
        )
    finally:
        list_path.unlink(missing_ok=True)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
