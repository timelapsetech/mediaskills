# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Get video resolution of a media file."""

from __future__ import annotations

import argparse

from _mediaskills_common import (
    add_input_arg,
    emit_success,
    main_wrapper,
    require_cmd,
    run,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_input_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "inspect.resolution"
    path = validate_input_path(args.input, op)
    require_cmd("ffprobe", op)
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(path),
        ],
        op,
    )
    wh = (result.stdout.strip().split("x") + ["", ""])[:2]
    width = int(wh[0]) if wh[0] else None
    height = int(wh[1]) if wh[1] else None
    emit_success(op, {"width": width, "height": height})


if __name__ == "__main__":
    main_wrapper(main)
