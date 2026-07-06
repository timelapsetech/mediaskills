# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Detect silence regions in an audio file."""

from __future__ import annotations

import argparse
import re
import subprocess

from _mediaskills_common import (
    add_input_arg,
    emit_success,
    main_wrapper,
    require_cmd,
    validate_input_path,
)

_SILENCE_START = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*([\d.]+)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run silence_detect.py --input track.wav",
    )
    add_input_arg(parser)
    return parser


def parse_silence_log(log: str) -> dict[str, list[float]]:
    starts: list[float] = []
    ends: list[float] = []
    for line in log.splitlines():
        m = _SILENCE_START.search(line)
        if m:
            starts.append(float(m.group(1)))
            continue
        m = _SILENCE_END.search(line)
        if m:
            ends.append(float(m.group(1)))
    return {"silence_starts": starts, "silence_ends": ends}


def main() -> None:
    args = build_parser().parse_args()
    op = "audio.silence_detect"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    result = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-30dB:d=0.5",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    log = (result.stderr or "") + (result.stdout or "")
    data = parse_silence_log(log)
    emit_success(op, data)


if __name__ == "__main__":
    main_wrapper(main)
