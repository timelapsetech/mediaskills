# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Return the JSON schema for labeled segment manifests."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_success, main_wrapper

OP = "program_master.schema"


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run schema.py",
    )


def main() -> None:
    build_parser().parse_args()
    emit_success(
        OP,
        {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "duration": {"type": "number"},
                "fps": {"type": "number"},
                "probe_offset_seconds": {"type": "number"},
                "black_silence_gaps": {"type": "array"},
                "probes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "gap_index": {"type": "integer"},
                            "probe_time": {"type": "number"},
                            "frame_path": {"type": "string"},
                            "classification": {"type": "object"},
                        },
                    },
                },
                "segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "start": {"type": "number"},
                            "end": {"type": "number"},
                            "duration": {"type": "number"},
                            "start_timecode": {"type": "string"},
                            "end_timecode": {"type": "string"},
                            "segment_type": {"type": "string", "enum": ["content", "gap"]},
                            "label": {"type": "string"},
                            "label_source": {"type": "string"},
                            "slate_text": {"type": "string"},
                            "probe_frame_path": {"type": "string"},
                        },
                    },
                },
                "silences": {"type": "array"},
                "blacks": {"type": "array"},
            },
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
