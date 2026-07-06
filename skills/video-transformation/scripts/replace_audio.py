# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Replace a video's audio track with an external audio file."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from _encode_opts import ffmpeg_error_tail, normalize_encode_options, video_encode_args
from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_progress,
    emit_success,
    is_truthy,
    main_wrapper,
    require_cmd,
    resolve_output,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run replace_audio.py --input video.mp4 --audio track.wav "
            "--copy-video"
        ),
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--audio",
        required=True,
        help="Path to replacement audio file",
    )
    parser.add_argument("--codec", default="libx264", help="Video encoder or copy")
    parser.add_argument("--bitrate", help="Video bitrate e.g. 1M")
    parser.add_argument("--crf", type=float, help="Video CRF when no bitrate")
    parser.add_argument("--preset", default="fast", help="Encoder preset")
    parser.add_argument("--audio-codec", default="aac", help="Output audio codec")
    parser.add_argument(
        "--copy-video",
        action="store_true",
        help="Copy video stream without re-encoding",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "video.replace_audio"
    video = validate_input_path(args.input, op)
    audio = Path(args.audio).expanduser()
    if not audio.is_file():
        emit_error(op, f"Audio not found: {args.audio}", code=EXIT_BAD_ARGS)
    require_cmd("ffmpeg", op)

    opts = normalize_encode_options(
        codec=args.codec,
        bitrate=args.bitrate,
        crf=args.crf,
        preset=args.preset,
        audio_codec=args.audio_codec,
        copy_video=is_truthy(args.copy_video),
    )
    out = resolve_output(str(video), "_audio_replaced.mp4", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    ff_args = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:a",
        opts["audio_codec"],
        "-shortest",
        "-movflags",
        "+faststart",
    ]
    ff_args.extend(video_encode_args(opts))
    ff_args.append(str(out))

    emit_progress("muxing", 10)
    err_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
    err_path = err_file.name
    err_file.close()

    result = subprocess.run(ff_args, capture_output=True, text=True)
    Path(err_path).write_text((result.stderr or result.stdout or ""), errors="replace")

    if result.returncode != 0:
        emit_error(op, ffmpeg_error_tail(err_path))
    Path(err_path).unlink(missing_ok=True)

    if not out.is_file():
        emit_error(op, "Replace-audio finished but output file is missing")

    emit_progress("done", 100)
    emit_success(
        op,
        {
            "output_path": str(out),
            "video_path": str(video),
            "audio_path": str(audio),
            "codec": opts["codec"],
            "bitrate": opts["bitrate"],
            "preset": opts["preset"],
        },
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
