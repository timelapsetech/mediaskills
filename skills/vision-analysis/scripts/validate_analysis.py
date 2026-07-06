# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Validate a frame analysis JSON document before running report scripts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _analysis_lib import validate_analysis_document
from _mediaskills_common import emit_error, emit_success, main_wrapper

OP = "vision.validate_analysis"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run validate_analysis.py --analysis-path frame_analysis.json",
    )
    parser.add_argument("--analysis-path", required=True, help="Frame analysis JSON to validate")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = Path(args.analysis_path)
    if not path.is_file():
        emit_error(OP, f"Analysis file not found: {path}", code=1)

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        emit_error(OP, f"Invalid JSON: {e}", code=1)

    errors = validate_analysis_document(doc)
    if errors:
        emit_error(OP, "; ".join(errors[:10]), code=1)

    emit_success(
        OP,
        {
            "analysis_path": str(path),
            "frame_count": doc.get("frame_count", len(doc.get("frames") or [])),
            "analyzed_count": doc.get("analyzed_count", 0),
            "valid": True,
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
