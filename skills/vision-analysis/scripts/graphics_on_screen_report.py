# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Graphics on screen report: all text types except burned-in subtitles."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_error, emit_success, main_wrapper
from _report_lib import (
    analysis_stem,
    build_condensed_rows,
    load_analysis_resolved,
    maybe_emit_reused_report,
    parse_type_list,
    write_report_files,
)

OP = "vision.graphics_on_screen_report"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run graphics_on_screen_report.py --analysis-path clip_frame_analysis.json",
    )
    parser.add_argument("--analysis-path", required=True, help="Frame analysis JSON from merge_analysis.py")
    parser.add_argument("--manifest-path", help="Optional manifest for analysis path resolution")
    parser.add_argument("--include-types", help="Comma-separated text_type filter")
    parser.add_argument("--exclude-types", help="Comma-separated text_type exclusion")
    parser.add_argument("--force", action="store_true", help="Regenerate even if report exists")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        analysis, resolved = load_analysis_resolved(args.analysis_path, args.manifest_path)
    except Exception as e:
        emit_error(OP, str(e))

    include = parse_type_list(args.include_types)
    exclude = parse_type_list(args.exclude_types)
    if include is None and exclude is None:
        exclude = {"subtitle"}

    if maybe_emit_reused_report(
        OP, args.force, str(resolved), "graphics_on_screen", include, exclude
    ):
        return

    rows = build_condensed_rows(analysis, include, exclude)
    columns = [
        "start_timecode",
        "end_timecode",
        "text_type",
        "text",
        "location",
        "shot_index",
        "start_seconds",
        "end_seconds",
    ]
    meta = {
        "report_type": "graphics_on_screen",
        "analysis_path": str(resolved),
        "input_path": analysis.get("input_path"),
        "include_types": sorted(include) if include else None,
        "exclude_types": sorted(exclude) if exclude else None,
    }
    outputs = write_report_files(
        analysis_stem(str(resolved)),
        "graphics_on_screen",
        rows,
        meta,
        columns,
        "Graphics on screen report",
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
