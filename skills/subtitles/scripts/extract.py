# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract embedded subtitle tracks from a video file to SRT."""

from __future__ import annotations

import argparse
import subprocess

from _mediaskills_common import (
    EXIT_PROCESSING,
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_progress,
    emit_success,
    main_wrapper,
    require_cmd,
    resolve_output,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run extract.py --input clip.mkv --output captions.srt",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "subtitles.extract"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)

    out = resolve_output(str(path), ".srt", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    emit_progress("extracting", 30)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-map", "0:s:0", str(out)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        emit_error(
            op,
            "No embedded subtitle track found. Use speech-captions transcribe for "
            "speech-to-text captions, or mux subtitles into the container first.",
            code=EXIT_PROCESSING,
        )

    emit_progress("done", 100)
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
