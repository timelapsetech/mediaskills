# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Compile a labeled segment manifest into agent-ready Markdown and JSON reports."""

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
from _report_lib import build_report, render_markdown_report

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
        help="Optional path for compiled report JSON (default: auto-generated)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    structure_path = args.structure_path
    if not structure_path or not Path(structure_path).is_file():
        emit_error(OP, "Provide --structure-path from label_segments.py or analyze_structure.py", code=1)

    manifest = json.loads(Path(structure_path).read_text(encoding="utf-8"))
    source = manifest.get("input_path") or "program"
    report = build_report(manifest)

    md = resolve_output(source, "_program_master.md", args.output)
    md.write_text(render_markdown_report(report), encoding="utf-8")

    out_json = resolve_output(source, "_program_master_report.json", args.json_output)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    emit_success(
        OP,
        {
            "output_path": str(md),
            "json_path": str(out_json),
            "segment_count": report.get("segment_count"),
            "rows": report.get("rows"),
            "episode": report.get("episode"),
        },
        [str(md), str(out_json)],
    )


if __name__ == "__main__":
    main_wrapper(main)
