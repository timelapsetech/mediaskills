# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Trim a video to a start/end time range."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from _mediaskills_common import (
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
from _encode_opts import ffmpeg_error_tail


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run trim.py --input clip.mp4 --start 1 --end 5",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--start", type=float, required=True, help="Start time in seconds")
    parser.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Force re-encode instead of stream copy",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "video.trim"
    if args.end <= args.start:
        emit_error(op, "end must be greater than start", code=1)
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    out = resolve_output(str(path), "_trim.mp4", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    emit_progress("trimming", 50)
    err_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
    err_path = err_file.name
    err_file.close()

    def run_ffmpeg(extra: list[str]) -> int:
        cmd = ["ffmpeg", "-y", "-ss", str(args.start), "-to", str(args.end), "-i", str(path), *extra, str(out)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        Path(err_path).write_text((result.stderr or result.stdout or ""), errors="replace")
        return result.returncode

    code = 0 if args.reencode else run_ffmpeg(["-c", "copy"])
    if code != 0:
        code = run_ffmpeg([])

    if code != 0:
        emit_error(op, ffmpeg_error_tail(err_path))
    Path(err_path).unlink(missing_ok=True)

    if not out.is_file():
        emit_error(op, "Trim finished but output file is missing")

    emit_progress("done", 100)
    emit_success(
        op,
        {"output_path": str(out), "start": args.start, "end": args.end},
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
