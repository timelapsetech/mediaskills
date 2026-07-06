# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Flag captions that may collide with lower-thirds or busy lower-screen zones."""

from __future__ import annotations

import argparse
import json

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
        epilog="Example: uv run apply-busy-zones.py --input captions.srt",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--report",
        help="JSON report path (default: auto-generated alongside SRT output)",
    )
    return parser


def flag_busy_zones(cues: list[dict], max_chars: int = 42) -> list[dict]:
    flagged: list[dict] = []
    for i, cue in enumerate(cues):
        chars = len(cue["text"].replace("\n", ""))
        if chars > max_chars or cue["text"].count("\n") >= 1:
            flagged.append(
                {
                    "index": i + 1,
                    "start": cue["start"],
                    "end": cue["end"],
                    "reason": "long_or_multiline",
                    "suggestion": "Consider top-safe placement / shorter lines",
                }
            )
    return flagged


def main() -> None:
    args = build_parser().parse_args()
    op = "caption.apply_busy_zones"
    path = validate_input_path(args.input, op)
    cues = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    flagged = flag_busy_zones(cues)
    out_srt = resolve_output(str(path), "_busy_zones.srt", args.output)
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    out_srt.write_text(cues_to_srt(cues), encoding="utf-8")
    report = (
        resolve_output(str(path), "_busy_zones.json", args.report)
        if args.report
        else out_srt.with_name(out_srt.stem + "_report.json")
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps({"flagged": flagged, "count": len(flagged)}, indent=2),
        encoding="utf-8",
    )
    emit_success(
        op,
        {
            "output_path": str(out_srt),
            "report_path": str(report),
            "flagged_count": len(flagged),
            "flagged": flagged,
        },
        [str(out_srt), str(report)],
    )


if __name__ == "__main__":
    main_wrapper(main)
