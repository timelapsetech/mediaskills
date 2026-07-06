# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Convert subtitle files between SRT and WebVTT."""

from __future__ import annotations

import argparse
from pathlib import Path

from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_input_arg,
    add_output_arg,
    cues_to_srt,
    cues_to_vtt,
    emit_error,
    emit_success,
    main_wrapper,
    parse_srt,
    parse_srt_ts,
    resolve_output,
    validate_input_path,
)


def parse_vtt(text: str) -> list[dict[str, object]]:
    text = text.replace("\r", "")
    lines = text.splitlines()
    cues: list[dict[str, object]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            i += 1
            continue
        if "-->" in line:
            start_s, end_s = [p.strip().split()[0] for p in line.split("-->", 1)]
            i += 1
            body_lines: list[str] = []
            while i < len(lines) and lines[i].strip():
                body_lines.append(lines[i].rstrip())
                i += 1
            body = "\n".join(body_lines).strip()
            if body:
                cues.append(
                    {
                        "start": parse_srt_ts(start_s),
                        "end": parse_srt_ts(end_s),
                        "text": body,
                    }
                )
            continue
        i += 1
    return cues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run convert.py --input captions.srt --format vtt",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--format",
        "-f",
        default="vtt",
        choices=["srt", "vtt"],
        help="Target subtitle format (default: vtt)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "subtitles.convert"
    path = validate_input_path(args.input, op)
    fmt = args.format.lower().lstrip(".")

    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".vtt" or raw.lstrip().startswith("WEBVTT"):
        cues = parse_vtt(raw)
    else:
        cues = parse_srt(raw)

    if not cues:
        emit_error(op, "No subtitle cues found in input file", code=EXIT_BAD_ARGS)

    out = resolve_output(str(path), f".{fmt}", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "vtt":
        out.write_text(cues_to_vtt(cues), encoding="utf-8")
    else:
        out.write_text(cues_to_srt(cues), encoding="utf-8")

    emit_success(
        op,
        {"output_path": str(out), "format": fmt, "cue_count": len(cues)},
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
