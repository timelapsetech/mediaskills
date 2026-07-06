# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Forced narrative report: burned-in subtitles only (text_type=subtitle)."""

from __future__ import annotations

import argparse
from pathlib import Path

from _forced_narrative_lib import (
    _embedded_tc_from_probe,
    build_dialogue_rows_from_analysis,
    write_forced_narrative_report_files,
)
from _mediaskills_common import emit_error, emit_success, main_wrapper
from _report_lib import (
    analysis_stem,
    load_analysis_resolved,
    maybe_emit_reused_report,
)

OP = "vision.forced_narrative_report"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run forced_narrative_report.py --analysis-path clip_frame_analysis.json",
    )
    parser.add_argument("--analysis-path", required=True, help="Frame analysis JSON from merge_analysis.py")
    parser.add_argument("--manifest-path", help="Optional manifest for analysis path resolution")
    parser.add_argument("--force", action="store_true", help="Regenerate even if report exists")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        analysis, resolved = load_analysis_resolved(args.analysis_path, args.manifest_path)
    except Exception as e:
        emit_error(OP, str(e))

    if maybe_emit_reused_report(
        OP, args.force, str(resolved), "forced_narrative", {"subtitle"}, None
    ):
        return

    input_path = analysis.get("input_path")
    embedded_fn = None
    embedded_meta = None
    if input_path:
        embedded_fn, embedded_meta = _embedded_tc_from_probe(str(input_path))

    rows = build_dialogue_rows_from_analysis(analysis, embedded_tc_fn=embedded_fn)
    meta = {
        "report_type": "forced_narrative",
        "analysis_path": str(resolved),
        "input_path": input_path,
        "input_name": analysis.get("input_name") or (Path(input_path).name if input_path else None),
        "embedded_timecode": embedded_meta,
        "include_types": ["subtitle"],
    }
    outputs = write_forced_narrative_report_files(
        analysis_stem(str(resolved)),
        rows,
        meta,
    )
    emit_success(
        OP,
        {
            "analysis_path": str(resolved),
            "output_path": str(outputs[0]),
            "report_path": str(outputs[0]),
            "json_path": str(outputs[1]),
            "csv_path": str(outputs[2]),
            "row_count": len(rows),
        },
        [str(p) for p in outputs],
    )


if __name__ == "__main__":
    main_wrapper(main)
