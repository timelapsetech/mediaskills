# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Forced narrative report: burned-in subtitles only (text_type=subtitle)."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_error, emit_success, main_wrapper
from _report_lib import (
    analysis_stem,
    build_condensed_rows,
    load_analysis_resolved,
    maybe_emit_reused_report,
    write_report_files,
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

    rows = build_condensed_rows(analysis, include_types={"subtitle"})
    columns = [
        "start_timecode",
        "end_timecode",
        "text",
        "shot_index",
        "start_seconds",
        "end_seconds",
        "confidence",
    ]
    meta = {
        "report_type": "forced_narrative",
        "analysis_path": str(resolved),
        "input_path": analysis.get("input_path"),
        "include_types": ["subtitle"],
    }
    outputs = write_report_files(
        analysis_stem(str(resolved)),
        "forced_narrative",
        rows,
        meta,
        columns,
        "Forced narrative (burned-in subtitles) report",
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
