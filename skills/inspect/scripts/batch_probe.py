# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Probe multiple files and return a table of metadata."""

from __future__ import annotations

import argparse
from pathlib import Path

from _mediaskills_common import (
    emit_error,
    emit_success,
    ffprobe_json,
    main_wrapper,
    summarize_probe,
    EXIT_BAD_ARGS,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="One or more media file paths",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "inspect.batch_probe"
    rows: list[dict] = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_file():
            rows.append({"path": raw, "filename": path.name, "error": "file not found"})
            continue
        try:
            probe = ffprobe_json(str(path), op)
            summary = summarize_probe(probe)
            fmt = probe.get("format", {})
            rows.append(
                {
                    "path": str(path),
                    "filename": path.name,
                    "duration_seconds": float(fmt.get("duration", 0) or 0),
                    "size_bytes": int(fmt.get("size", 0) or 0),
                    "format": summary.get("format"),
                    "video": summary.get("video"),
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            rows.append({"path": str(path), "filename": path.name, "error": str(e)})
    emit_success(op, {"rows": rows})


if __name__ == "__main__":
    main_wrapper(main)
