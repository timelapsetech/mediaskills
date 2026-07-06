# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Shift subtitle cue timings by a fixed offset in seconds."""

from __future__ import annotations

import argparse

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
    resolve_output,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run shift.py --input captions.srt --offset-seconds 1.5",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--offset-seconds",
        type=float,
        required=True,
        help="Seconds to add to every cue (negative values shift earlier)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "subtitles.shift"
    path = validate_input_path(args.input, op)
    offset = float(args.offset_seconds)

    raw = path.read_text(encoding="utf-8", errors="replace")
    if "WEBVTT" in raw:
        cues = parse_srt(raw.replace("WEBVTT", "").replace(".", ","))
    else:
        cues = parse_srt(raw)

    if not cues:
        emit_error(op, "No subtitle cues found in input file", code=EXIT_BAD_ARGS)

    for cue in cues:
        cue["start"] = max(0.0, float(cue["start"]) + offset)
        cue["end"] = max(float(cue["start"]) + 0.1, float(cue["end"]) + offset)

    ext = ".vtt" if path.suffix.lower() == ".vtt" else ".srt"
    out = resolve_output(str(path), f"_shift{ext}", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".vtt":
        out.write_text(cues_to_vtt(cues), encoding="utf-8")
    else:
        out.write_text(cues_to_srt(cues), encoding="utf-8")

    emit_success(
        op,
        {"output_path": str(out), "offset_seconds": offset, "cue_count": len(cues)},
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
