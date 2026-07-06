# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Validate SRT/VTT caption files for timing, overlap, and readability issues."""

from __future__ import annotations

import argparse
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    emit_success,
    main_wrapper,
    parse_srt,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run validate.py --input captions.srt",
    )
    add_input_arg(parser)
    return parser


def validate_cues(cues: list[dict]) -> list[str]:
    issues: list[str] = []
    if not cues:
        issues.append("No cues parsed")
        return issues
    for i, cue in enumerate(cues):
        if cue["end"] <= cue["start"]:
            issues.append(f"Cue {i + 1}: end <= start")
        if i > 0 and cue["start"] < cues[i - 1]["end"]:
            issues.append(f"Cue {i + 1}: overlaps previous cue")
        if len(cue["text"]) > 80:
            issues.append(f"Cue {i + 1}: long line ({len(cue['text'])} chars)")
        if cue["end"] - cue["start"] < 0.5:
            issues.append(f"Cue {i + 1}: very short duration")
    return issues


def main() -> None:
    args = build_parser().parse_args()
    op = "caption.validate"
    path = validate_input_path(args.input, op)
    raw = path.read_text(encoding="utf-8", errors="replace")
    if raw.lstrip().startswith("WEBVTT"):
        raw = raw.replace("WEBVTT\n", "", 1)
    cues = parse_srt(raw)
    issues = validate_cues(cues)
    emit_success(
        op,
        {
            "valid": len(issues) == 0,
            "cue_count": len(cues),
            "issues": issues,
            "input_path": str(path),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
