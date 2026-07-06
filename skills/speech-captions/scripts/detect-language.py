# /// script
# requires-python = ">=3.11"
# dependencies = ["faster-whisper>=1.0.3"]
# ///

"""Detect the spoken language in an audio or video file."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    emit_progress,
    emit_success,
    main_wrapper,
    require_cmd,
    run,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run detect-language.py --input clip.mp4",
    )
    add_input_arg(parser)
    parser.add_argument(
        "--model",
        "-m",
        default="tiny",
        help="faster-whisper model size (default: tiny)",
    )
    parser.add_argument(
        "--sample-seconds",
        type=float,
        default=60.0,
        help="Seconds of audio to analyze (default: 60)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "speech_captions.detect_language"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)

    emit_progress("extracting", 20)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "sample.wav"
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-t",
                str(args.sample_seconds),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(wav),
            ],
            op,
        )

        from faster_whisper import WhisperModel

        model = WhisperModel(args.model, device="cpu", compute_type="int8")
        emit_progress("detecting", 60)
        _, info = model.transcribe(str(wav), beam_size=1)
        lang = getattr(info, "language", None)
        prob = getattr(info, "language_probability", None)

        emit_progress("done", 100)
        emit_success(
            op,
            {
                "language": lang,
                "probability": prob,
                "input_path": str(path),
                "model": args.model,
                "sample_seconds": args.sample_seconds,
            },
        )


if __name__ == "__main__":
    main_wrapper(main)
