# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Convert plain text or timed segments to a WebVTT subtitle file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_output_arg,
    cues_to_vtt,
    emit_error,
    emit_success,
    main_wrapper,
    resolve_output,
    text_to_cues,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run to-vtt.py --text 'Hello world.' --duration 5",
    )
    parser.add_argument(
        "--input",
        "-i",
        default="transcript",
        help="Stem used for auto-generated output naming (default: transcript)",
    )
    add_output_arg(parser)
    parser.add_argument("--text", "-t", help="Plain text to split into timed cues")
    parser.add_argument(
        "--segments-json",
        help="Path to JSON file with [{start, end, text}, ...] segments",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Total duration in seconds when splitting --text (default: estimated)",
    )
    return parser


def load_segments(path: str) -> list[dict[str, object]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "segments" in data:
        data = data["segments"]
    if not isinstance(data, list):
        raise ValueError("segments JSON must be a list or object with a segments array")
    cues: list[dict[str, object]] = []
    for item in data:
        cues.append(
            {
                "start": float(item["start"]),
                "end": float(item["end"]),
                "text": str(item["text"]),
            }
        )
    return cues


def main() -> None:
    args = build_parser().parse_args()
    op = "speech_captions.to_vtt"

    if args.segments_json:
        cues = load_segments(args.segments_json)
    elif args.text:
        duration = args.duration
        if duration is None:
            duration = max(5.0, len(args.text.split()) * 0.4)
        cues = text_to_cues(args.text, duration)
    else:
        emit_error(op, "Provide --text or --segments-json", code=EXIT_BAD_ARGS)

    out = resolve_output(args.input, ".vtt", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cues_to_vtt(cues), encoding="utf-8")
    emit_success(op, {"output_path": str(out), "cue_count": len(cues)}, [str(out)])


if __name__ == "__main__":
    main_wrapper(main)
