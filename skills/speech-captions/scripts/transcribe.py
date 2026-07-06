# /// script
# requires-python = ">=3.11"
# dependencies = ["faster-whisper>=1.0.3"]
# ///

"""Transcribe audio/video to text, timed segments, SRT, and JSON."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    cues_to_srt,
    emit_progress,
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
        epilog="Example: uv run transcribe.py --input clip.mp4 --model tiny",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--model",
        "-m",
        default="tiny",
        help="faster-whisper model size (default: tiny)",
    )
    parser.add_argument(
        "--json-output",
        help="Path for transcript JSON (default: auto-generated alongside SRT)",
    )
    return parser


def extract_wav(src: str, dst: Path, op: str) -> None:
    run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", str(dst)], op)


def main() -> None:
    args = build_parser().parse_args()
    op = "speech_captions.transcribe"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)

    emit_progress("extracting audio", 10)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extract_wav(str(path), wav, op)

        emit_progress("loading model", 25)
        from faster_whisper import WhisperModel

        model = WhisperModel(args.model, device="cpu", compute_type="int8")

        emit_progress("transcribing", 40)
        segments_iter, info = model.transcribe(str(wav), beam_size=1)
        segments: list[dict[str, object]] = []
        cues: list[dict[str, object]] = []
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if not text:
                continue
            entry = {"start": seg.start, "end": seg.end, "text": text}
            segments.append(entry)
            cues.append(entry)

        full_text = " ".join(str(s["text"]) for s in segments).strip()
        srt_path = resolve_output(str(path), ".srt", args.output)
        json_path = (
            Path(args.json_output)
            if args.json_output
            else resolve_output(str(path), "_transcript.json")
        )
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text(cues_to_srt(cues), encoding="utf-8")
        json_path.write_text(
            json.dumps(
                {
                    "text": full_text,
                    "segments": segments,
                    "language": getattr(info, "language", None),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        emit_progress("done", 100)
        emit_success(
            op,
            {
                "text": full_text,
                "segments": segments,
                "language": getattr(info, "language", None),
                "duration": getattr(info, "duration", None),
                "output_path": str(srt_path),
                "srt_path": str(srt_path),
                "json_path": str(json_path),
                "model": args.model,
                "cue_count": len(cues),
            },
            [str(srt_path), str(json_path)],
        )


if __name__ == "__main__":
    main_wrapper(main)
