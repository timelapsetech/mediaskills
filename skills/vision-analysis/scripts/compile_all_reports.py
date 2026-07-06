# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Index all OCR on-screen text reports in the generated output directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import (
    add_output_arg,
    emit_success,
    generated_dir,
    main_wrapper,
    resolve_output,
)

OP = "vision.compile_all_reports"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run compile_all_reports.py",
    )
    add_output_arg(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = generated_dir()
    reports = sorted(root.glob("*_onscreen_text_*.json"))
    rows = []
    for path in reports:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows.append(
                {
                    "path": str(path),
                    "input_path": data.get("input_path"),
                    "detection_count": data.get("detection_count") or len(data.get("rows") or []),
                }
            )
        except Exception:
            rows.append({"path": str(path)})

    out = resolve_output("vision", "_all_reports.md", args.output)
    lines = ["# Vision reports index", "", f"Found {len(rows)} report(s).", ""]
    for row in rows:
        lines.append(f"- `{row.get('path')}` — {row.get('detection_count', '?')} detections")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    emit_success(
        OP,
        {"output_path": str(out), "reports": rows, "count": len(rows)},
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)
