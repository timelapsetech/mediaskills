# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract text from title cards and graphic screens."""

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

OP = "vision.extract_title_text"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run extract_title_text.py --analysis-path clip_frame_analysis.json",
    )
    parser.add_argument("--analysis-path", required=True, help="Frame analysis JSON from merge_analysis.py")
    parser.add_argument("--manifest-path", help="Optional manifest for analysis path resolution")
    parser.add_argument(
        "--include-types",
        help="Comma-separated text_type filter (default: title,graphic)",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate even if report exists")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        analysis, resolved = load_analysis_resolved(args.analysis_path, args.manifest_path)
    except Exception as e:
        emit_error(OP, str(e))

    include = parse_type_list(args.include_types)
    if include is None:
        include = {"title", "graphic"}

    if maybe_emit_reused_report(OP, args.force, str(resolved), "title_text", include, None):
        return

    rows = build_condensed_rows(analysis, include_types=include)

    seen: set[str] = set()
    unique_rows: list[dict] = []
    texts: list[str] = []
    for row in rows:
        key = " ".join((row.get("text") or "").lower().split())
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
        texts.append(row.get("text") or "")

    columns = [
        "start_timecode",
        "end_timecode",
        "text_type",
        "text",
        "shot_index",
        "start_seconds",
        "end_seconds",
    ]
    meta = {
        "report_type": "title_text",
        "analysis_path": str(resolved),
        "input_path": analysis.get("input_path"),
        "include_types": sorted(include),
        "texts": texts,
    }
    outputs = write_report_files(
        analysis_stem(str(resolved)),
        "title_text",
        unique_rows,
        meta,
        columns,
        "Title and graphic text extraction",
    )
    emit_success(
        OP,
        {
            "analysis_path": str(resolved),
            "output_path": str(outputs[0]),
            "report_path": str(outputs[0]),
            "json_path": str(outputs[1]),
            "csv_path": str(outputs[2]),
            "row_count": len(unique_rows),
            "text_count": len(texts),
        },
        [str(p) for p in outputs],
    )


if __name__ == "__main__":
    main_wrapper(main)
