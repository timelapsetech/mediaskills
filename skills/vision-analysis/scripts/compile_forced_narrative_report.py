# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Build a forced-narrative (burned-in dialogue) report from OCR on-screen text JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _forced_narrative_lib import (
    _embedded_tc_from_probe,
    build_dialogue_rows_from_detections,
    write_forced_narrative_report_files,
)
from _mediaskills_common import emit_error, emit_success, main_wrapper, validate_input_path

OP = "vision.compile_forced_narrative_report"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run compile_forced_narrative_report.py "
            "--onscreen-json .mediaskills/generated/clip_onscreen_text.json "
            "--input /path/to/clip.mov"
        ),
    )
    parser.add_argument(
        "--onscreen-json",
        required=True,
        help="On-screen text JSON from compile_report.py",
    )
    parser.add_argument(
        "--input",
        help="Source video (for embedded SMPTE TC mapping via tmcd)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    src = Path(args.onscreen_json)
    if not src.is_file():
        emit_error(OP, f"On-screen JSON not found: {src}", code=1)

    doc = json.loads(src.read_text(encoding="utf-8"))
    detections = doc.get("rows") or []
    input_path = args.input or doc.get("input_path")
    embedded_meta = None
    embedded_fn = None
    if input_path:
        video = validate_input_path(input_path, OP)
        input_path = str(video.resolve())
        embedded_fn, embedded_meta = _embedded_tc_from_probe(input_path)

    rows = build_dialogue_rows_from_detections(detections, embedded_tc_fn=embedded_fn)
    stem = src.stem.replace("_onscreen_text", "").split("_onscreen_text_")[0]
    if stem.endswith("_onscreen_text"):
        stem = stem[: -len("_onscreen_text")]

    meta = {
        "input_path": input_path or doc.get("input_path"),
        "input_name": doc.get("input_name") or Path(input_path or src).name,
        "onscreen_json_path": str(src.resolve()),
        "embedded_timecode": embedded_meta,
        "duration_seconds": doc.get("duration_seconds"),
        "interval_seconds": doc.get("interval_seconds"),
    }
    outputs = write_forced_narrative_report_files(stem, rows, meta)
    emit_success(
        OP,
        {
            "onscreen_json_path": str(src.resolve()),
            "output_path": str(outputs[0]),
            "report_path": str(outputs[0]),
            "json_path": str(outputs[1]),
            "csv_path": str(outputs[2]),
            "row_count": len(rows),
            "rows": rows,
        },
        [str(p) for p in outputs],
    )


if __name__ == "__main__":
    main_wrapper(main)
