# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "faster-whisper>=1.0.3",
# ]
# ///

"""Transcribe media to SRT captions (Whisper via faster-whisper)."""

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
    format_srt_ts,
    main_wrapper,
    require_cmd,
    resolve_output,
    validate_input_path,
)

OP = "caption.to_captions_pipeline"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run to-captions-pipeline.py --input clip.mp4 --model tiny",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--model",
        default="tiny",
        help="Whisper model size (default: tiny)",
    )
    return parser


def extract_audio(input_path: Path, wav_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav_path),
        ],
        check=True,
        capture_output=True,
    )


def segments_to_srt(segments) -> str:
    lines: list[str] = []
    idx = 1
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{format_srt_ts(seg.start)} --> {format_srt_ts(seg.end)}")
        lines.append(text)
        lines.append("")
        idx += 1
    if not lines:
        lines = [
            "1",
            "00:00:00,000 --> 00:00:02,000",
            "[No speech detected]",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    out_srt = resolve_output(str(path), "_captions.srt", args.output)
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    model_size = args.model

    try:
        emit_progress("extracting audio", 10)
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "audio.wav"
            extract_audio(path, wav_path)

            emit_progress("loading whisper", 25)
            from faster_whisper import WhisperModel

            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            emit_progress("transcribing", 40)
            segments, info = model.transcribe(str(wav_path), beam_size=1)
            segment_list = list(segments)
            emit_progress("writing srt", 85)
            out_srt.write_text(segments_to_srt(segment_list), encoding="utf-8")

        emit_progress("done", 100)
        emit_success(
            OP,
            {
                "output_path": str(out_srt),
                "subtitle_path": str(out_srt),
                "language": getattr(info, "language", None),
                "duration": getattr(info, "duration", None),
                "segment_count": len(segment_list),
                "model": model_size,
            },
            [str(out_srt)],
        )
    except FileNotFoundError as e:
        emit_error(OP, f"Missing dependency: {e}")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace")[:500]
        emit_error(OP, f"ffmpeg failed: {err}")
    except ImportError:
        emit_error(
            OP,
            "faster-whisper not installed. Run via `uv run` so PEP 723 dependencies resolve.",
        )
    except Exception as e:
        emit_error(OP, str(e))


if __name__ == "__main__":
    main_wrapper(main)
