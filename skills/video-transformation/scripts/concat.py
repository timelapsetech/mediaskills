# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Concatenate video files end-to-end."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from _encode_opts import ffmpeg_error_tail
from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_output_arg,
    emit_error,
    emit_progress,
    emit_success,
    main_wrapper,
    require_cmd,
    resolve_output,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run concat.py --paths a.mp4 b.mp4 --output joined.mp4",
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="Input video paths in order (must exist)",
    )
    add_output_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "video.concat"
    require_cmd("ffmpeg", op)

    resolved: list[Path] = []
    for p in args.paths:
        path = Path(p).expanduser().resolve()
        if not path.is_file():
            emit_error(op, f"file not found: {path}", code=EXIT_BAD_ARGS)
        resolved.append(path)

    if args.output:
        out = Path(args.output).expanduser()
    else:
        out = resolve_output(str(resolved[0]), "_concat.mp4", None)
    out.parent.mkdir(parents=True, exist_ok=True)

    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    for p in resolved:
        safe = str(p).replace("'", "'\\''")
        list_file.write(f"file '{safe}'\n")
    list_path = list_file.name
    list_file.close()

    emit_progress("concat", 20)
    err_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
    err_path = err_file.name
    err_file.close()

    def run_concat(extra: list[str]) -> int:
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, *extra, str(out)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        Path(err_path).write_text((result.stderr or result.stdout or ""), errors="replace")
        return result.returncode

    code = run_concat(["-c", "copy"])
    if code != 0:
        code = run_concat(
            ["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart"]
        )

    Path(list_path).unlink(missing_ok=True)

    if code != 0:
        emit_error(op, ffmpeg_error_tail(err_path))
    Path(err_path).unlink(missing_ok=True)

    if not out.is_file():
        emit_error(op, "Concat finished but output file is missing")

    emit_progress("done", 100)
    paths_str = [str(p) for p in resolved]
    emit_success(
        op,
        {
            "output_path": str(out),
            "input_count": len(paths_str),
            "input_paths": paths_str,
        },
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
