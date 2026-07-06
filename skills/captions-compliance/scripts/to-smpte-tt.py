# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Export SRT cues to a minimal SMPTE-TT / TTML XML file."""

from __future__ import annotations

import argparse
import html

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_success,
    format_vtt_ts,
    main_wrapper,
    parse_srt,
    resolve_output,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run to-smpte-tt.py --input captions.srt",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    return parser


def cues_to_smpte_tt(cues: list[dict], lang: str = "en") -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<tt xml:lang="{lang}" xmlns="http://www.w3.org/ns/ttml">',
        "  <body>",
        "    <div>",
    ]
    for cue in cues:
        begin = format_vtt_ts(cue["start"])
        end = format_vtt_ts(cue["end"])
        text = html.escape(cue["text"]).replace("\n", "<br/>")
        parts.append(f'      <p begin="{begin}" end="{end}">{text}</p>')
    parts.extend(["    </div>", "  </body>", "</tt>", ""])
    return "\n".join(parts)


def main() -> None:
    args = build_parser().parse_args()
    op = "caption.to_smpte_tt"
    path = validate_input_path(args.input, op)
    cues = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    content = cues_to_smpte_tt(cues)
    out = resolve_output(str(path), ".xml", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    emit_success(
        op,
        {"output_path": str(out), "cue_count": len(cues), "format": "SMPTE-TT/TTML"},
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
