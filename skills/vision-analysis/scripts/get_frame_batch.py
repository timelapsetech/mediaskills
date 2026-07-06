# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Read a batch of frames from an interval or shot manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import emit_error, emit_success, main_wrapper

OP = "vision.get_frame_batch"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run get_frame_batch.py --manifest-path clip_interval_frames.json --batch-index 0",
    )
    parser.add_argument("--manifest-path", required=True, help="Path to frame manifest JSON")
    parser.add_argument("--batch-size", type=int, default=25, help="Frames per batch (default 25)")
    parser.add_argument("--batch-index", type=int, default=0, help="Zero-based batch index")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = Path(args.manifest_path)
    if not manifest_path.is_file():
        emit_error(OP, f"Missing or invalid manifest_path: {args.manifest_path}", code=1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = manifest.get("frames") or []
    batch_size = max(1, int(args.batch_size))
    batch_index = max(0, int(args.batch_index))
    start = batch_index * batch_size
    end = start + batch_size
    batch = frames[start:end]

    emit_success(
        OP,
        {
            "manifest_path": str(manifest_path),
            "batch_index": batch_index,
            "batch_size": batch_size,
            "total_frames": len(frames),
            "frames": batch,
            "has_more": end < len(frames),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
