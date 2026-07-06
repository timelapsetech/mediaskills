# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Convert audio to another format (wav, mp3, aac, flac, …)."""

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
        epilog="Example: uv run convert.py --input track.wav --format mp3",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--format",
        "-f",
        default="mp3",
        help="Output format/extension (default: mp3)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "audio.convert"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    fmt = args.format.lstrip(".")
    out = resolve_output(str(path), f".{fmt}", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-i", str(path), str(out)], op)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
