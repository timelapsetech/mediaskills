# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Compile a labeled segment manifest into Markdown and JSON reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import (
    add_output_arg,
    emit_error,
    emit_success,
    main_wrapper,
    resolve_output,
)

OP = "program_master.compile"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run compile.py --structure-path labeled_segments.json",
    )
    add_output_arg(parser)
    parser.add_argument(
        "--structure-path",
        "--manifest-path",
        dest="structure_path",
        required=True,
        help="Path to labeled segment JSON from label_segments.py",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path for compiled JSON copy (default: auto-generated)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    structure_path = args.structure_path
    if not structure_path or not Path(structure_path).is_file():
        emit_error(OP, "Provide --structure-path from label_segments.py or analyze_structure.py", code=1)

    data = json.loads(Path(structure_path).read_text(encoding="utf-8"))
    source = data.get("input_path") or "program"
    md = resolve_output(source, "_program_master.md", args.output)
    segments = data.get("segments") or []
    content_segments = [s for s in segments if s.get("segment_type") != "gap"]
    labeled = [
        s
        for s in content_segments
        if s.get("label") and s.get("label") not in ("unlabeled",)
    ]
    lines = [
        f"# Program master: {Path(source).name}",
        "",
        f"- Duration: {data.get('duration')}s",
        f"- Segments: {len(segments)}",
        f"- Content segments: {len(content_segments)}",
        f"- Labeled content segments: {len(labeled)}",
        f"- Black+silent gaps: {len(data.get('black_silence_gaps') or data.get('gaps') or [])}",
        f"- Silences: {len(data.get('silences') or [])}",
        f"- Blacks: {len(data.get('blacks') or [])}",
        "",
        "| # | Type | Start | End | Duration | Label | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for seg in segments:
        seg_type = seg.get("segment_type") or "content"
        lines.append(
            f"| {seg.get('index')} | {seg_type} | {seg.get('start_timecode', seg.get('start'))} | "
            f"{seg.get('end_timecode', seg.get('end'))} | {round(float(seg.get('duration') or 0), 3)}s | "
            f"{seg.get('label', '')} | {seg.get('label_source', '')} |"
        )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_json = resolve_output(source, "_program_master.json", args.json_output)
    out_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    emit_success(
        OP,
        {
            "output_path": str(md),
            "json_path": str(out_json),
            "segment_count": len(data.get("segments") or []),
            "rows": data.get("segments") or [],
        },
        [str(md), str(out_json)],
    )


if __name__ == "__main__":
    main_wrapper(main)
