# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""List frame manifests and vision reports in the generated output directory."""

from __future__ import annotations

import argparse
import json

from _mediaskills_common import emit_success, generated_dir, main_wrapper

OP = "vision.list_extractions"


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run list_extractions.py",
    )


def main() -> None:
    build_parser().parse_args()
    root = generated_dir()
    manifests = sorted(root.glob("*_interval_frames.json")) + sorted(
        root.glob("*interval_frames*.json")
    )
    analysis_files = sorted(root.glob("*frame_analysis*.json"))
    reports = sorted(root.glob("*_onscreen_text_*.md"))
    items = []

    seen_manifests: set[str] = set()
    for path in manifests:
        key = str(path)
        if key in seen_manifests:
            continue
        seen_manifests.add(key)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "type": "manifest",
                    "path": key,
                    "input_path": data.get("input_path"),
                    "frame_count": data.get("frame_count") or len(data.get("frames") or []),
                }
            )
        except Exception:
            items.append({"type": "manifest", "path": key})

    for path in analysis_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "type": "frame_analysis",
                    "path": str(path),
                    "manifest_path": data.get("manifest_path"),
                    "analyzed_count": data.get("analyzed_count"),
                }
            )
        except Exception:
            items.append({"type": "frame_analysis", "path": str(path)})

    for path in reports:
        items.append({"type": "report", "path": str(path)})

    emit_success(OP, {"items": items, "count": len(items)})


if __name__ == "__main__":
    main_wrapper(main)
