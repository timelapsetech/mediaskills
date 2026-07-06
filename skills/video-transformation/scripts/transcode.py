# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Transcode a video with explicit codec, bitrate, or CRF."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from _encode_opts import ffmpeg_error_tail, normalize_encode_options, video_encode_args
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run transcode.py --input clip.mp4 --codec libx264 --bitrate 1M",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--codec", default="libx264", help="Video encoder (default libx264)")
    parser.add_argument("--bitrate", help="Target video bitrate, e.g. 1M or 2500k")
    parser.add_argument("--crf", type=float, help="Constant rate factor (default 23 when no bitrate)")
    parser.add_argument("--preset", default="fast", help="x264/x265 preset (default fast)")
    parser.add_argument("--audio-codec", default="aac", help="Audio codec (default aac)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "video.transcode"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)

    opts = normalize_encode_options(
        codec=args.codec,
        bitrate=args.bitrate,
        crf=args.crf,
        preset=args.preset,
        audio_codec=args.audio_codec,
    )
    out = resolve_output(str(path), "_transcode.mp4", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    ff_args = ["ffmpeg", "-y", "-i", str(path)]
    ff_args.extend(video_encode_args(opts))
    ff_args.extend(["-c:a", opts["audio_codec"], "-movflags", "+faststart", str(out)])

    emit_progress("encoding", 10)
    err_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
    err_path = err_file.name
    err_file.close()

    result = subprocess.run(ff_args, capture_output=True, text=True)
    Path(err_path).write_text((result.stderr or result.stdout or ""), errors="replace")

    if result.returncode != 0:
        emit_error(op, ffmpeg_error_tail(err_path))
    Path(err_path).unlink(missing_ok=True)

    if not out.is_file():
        emit_error(op, "Transcode finished but output file is missing")

    emit_progress("done", 100)
    emit_success(
        op,
        {
            "output_path": str(out),
            "codec": opts["codec"],
            "bitrate": opts["bitrate"],
            "crf": opts["crf"],
            "preset": opts["preset"],
        },
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
