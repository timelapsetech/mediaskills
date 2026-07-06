# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Merge agent-produced frame analysis JSON into a frame analysis document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _analysis_lib import (
    build_frame_entry,
    default_analysis_path,
    find_existing_analysis_path,
    load_manifest,
    load_or_create_analysis,
    merge_frame_results,
    manifest_frame_lookup,
    normalize_agent_frame,
    resolve_manifest_path_from_analysis,
)
from _mediaskills_common import emit_error, emit_success, is_truthy, main_wrapper

OP = "vision.merge_analysis"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "The agent analyzes frame images (using its own vision capabilities), writes a JSON "
            "batch file, then this script merges results into *_frame_analysis_*.json for reports.\n\n"
            "Example:\n"
            "  uv run merge_analysis.py --manifest-path frames.json "
            "--frames-json batch0.json --analysis-path out.json"
        ),
    )
    parser.add_argument(
        "--manifest-path",
        help="Frame manifest JSON from extract_interval_frames or shots.extract_frames",
    )
    parser.add_argument(
        "--frames-json",
        required=True,
        help="JSON file with agent analysis for one or more frames ({\"frames\": [...]})",
    )
    parser.add_argument(
        "--analysis-path",
        help="Output analysis JSON (created or updated). Defaults to new file beside manifest.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing frame entries instead of merging",
    )
    return parser


def load_agent_frames(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        emit_error(OP, f"Invalid --frames-json: {e}", code=1)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("frames"), list):
        return data["frames"]
    emit_error(OP, "--frames-json must be {\"frames\": [...]} or a top-level array", code=1)


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = (args.manifest_path or "").strip()
    analysis_path_arg = (args.analysis_path or "").strip()

    if not manifest_path:
        if not analysis_path_arg:
            emit_error(OP, "--manifest-path or --analysis-path is required", code=1)
        manifest_path = resolve_manifest_path_from_analysis(analysis_path_arg) or ""
        if not manifest_path:
            emit_error(
                OP,
                f"Could not resolve manifest_path from analysis file: {analysis_path_arg}",
                code=1,
            )

    manifest = load_manifest(manifest_path, OP)
    manifest_frames = manifest["frames"]
    if not manifest_frames:
        emit_error(
            OP,
            "Manifest has no frames. Run extract_interval_frames or shots.extract_frames first.",
            code=3,
        )

    manifest_path = manifest["manifest_path"]
    frames_json = Path(args.frames_json)
    if not frames_json.is_file():
        emit_error(OP, f"--frames-json not found: {frames_json}", code=1)

    agent_frames = load_agent_frames(frames_json)
    if not agent_frames:
        emit_error(OP, "No frames in --frames-json", code=1)

    analysis_path = (
        Path(analysis_path_arg)
        if analysis_path_arg
        else find_existing_analysis_path(manifest_path) or default_analysis_path(manifest_path)
    )

    doc = load_or_create_analysis(analysis_path, manifest_path, manifest.get("input_path"))
    if is_truthy(args.force):
        doc["frames"] = []
        doc["analyzed_count"] = 0

    doc["frame_count"] = len(manifest_frames)
    doc["manifest_path"] = manifest_path
    if manifest.get("input_path"):
        doc["input_path"] = manifest["input_path"]

    lookup = manifest_frame_lookup(manifest_frames)
    batch_entries = [normalize_agent_frame(f, lookup) for f in agent_frames if isinstance(f, dict)]
    doc = merge_frame_results(doc, batch_entries)
    analysis_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    emit_success(
        OP,
        {
            "analysis_path": str(analysis_path),
            "manifest_path": manifest_path,
            "merged_frames": len(batch_entries),
            "analyzed_count": doc.get("analyzed_count", 0),
            "frame_count": doc.get("frame_count", 0),
            "complete": doc.get("analyzed_count", 0) >= doc.get("frame_count", 0),
        },
        [str(analysis_path)],
    )


if __name__ == "__main__":
    main_wrapper(main)
