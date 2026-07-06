# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract audio from a video file as MP3."""

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
        epilog="Example: uv run extract_audio.py --input clip.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "video.extract_audio"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    out = resolve_output(str(path), ".mp3", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    run(
        ["ffmpeg", "-y", "-i", str(path), "-vn", "-acodec", "libmp3lame", "-q:a", "2", str(out)],
        op,
    )
    emit_success(op, {"output_path": str(out)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
