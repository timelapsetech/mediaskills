# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Normalize SRT caption whitespace and soft-wrap long lines."""

from __future__ import annotations

import argparse

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    cues_to_srt,
    emit_success,
    main_wrapper,
    parse_srt,
    resolve_output,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run format.py --input captions.srt",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    return parser


def format_cue_text(text: str, max_chars: int = 84) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    mid = len(text) // 2
    split_at = text.rfind(" ", 0, mid)
    if split_at < 20:
        split_at = text.find(" ", mid)
    if split_at > 0:
        return text[:split_at].strip() + "\n" + text[split_at:].strip()
    return text


def main() -> None:
    args = build_parser().parse_args()
    op = "caption.format"
    path = validate_input_path(args.input, op)
    cues = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    for cue in cues:
        cue["text"] = format_cue_text(cue["text"])
    out = resolve_output(str(path), "_formatted.srt", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cues_to_srt(cues), encoding="utf-8")
    emit_success(
        op,
        {"output_path": str(out), "cue_count": len(cues)},
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
