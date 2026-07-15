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
            "required": [
                "schema_version",
                "algorithm_version",
                "input_path",
                "duration",
                "fps",
                "timecode_mode",
                "segments",
                "effective_config",
                "selected_streams",
                "provenance",
                "validation",
            ],
            "properties": {
                "schema_version": {"type": "string", "const": "2.0"},
                "algorithm_version": {"type": "string"},
                "input_path": {"type": "string"},
                "duration": {"type": "number"},
                "fps": {"oneOf": [{"type": "number"}, {"type": "string"}]},
                "timecode_mode": {"type": "string", "enum": ["embedded", "file"]},
                "embedded_timecode": {
                    "type": ["object", "null"],
                    "properties": {
                        "timecode": {"type": "string"},
                        "fps": {"oneOf": [{"type": "number"}, {"type": "string"}]},
                        "drop_frame": {"type": "boolean"},
                        "source": {"type": "string", "enum": ["tmcd", "container"]},
                        "stream_index": {"type": ["integer", "null"]},
                    },
                },
                "probe_offset_seconds": {"type": "number"},
                "black_detection": {
                    "type": "object",
                    "properties": {
                        "pixel_threshold": {"type": "number"},
                        "picture_threshold": {"type": "number"},
                        "fade_refine": {"type": "boolean"},
                        "fade_handle_frames": {"type": "integer"},
                        "boundary_policy": {"type": "string"},
                    },
                },
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
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": [
                            "index",
                            "start",
                            "end",
                            "duration",
                            "start_timecode",
                            "end_timecode",
                            "segment_type",
                        ],
                        "properties": {
                            "index": {"type": "integer"},
                            "start": {"type": "number"},
                            "end": {"type": "number"},
                            "duration": {"type": "number"},
                            "start_timecode": {"type": "string"},
                            "end_timecode": {"type": "string"},
                            "start_timecode_file": {"type": "string"},
                            "end_timecode_file": {"type": "string"},
                            "segment_type": {"type": "string", "enum": ["content", "gap"]},
                            "label": {"type": "string"},
                            "label_source": {"type": "string"},
                            "slate_text": {"type": "string"},
                            "probe_frame_path": {"type": "string"},
                            "boundary_evidence": {"type": "object"},
                        },
                    },
                },
                "silences": {"type": "array"},
                "blacks": {"type": "array"},
                "effective_config": {"type": "object"},
                "selected_streams": {"type": "object"},
                "provenance": {
                    "type": "object",
                    "required": ["skill", "source", "profile", "toolchain", "command"],
                },
                "validation": {
                    "type": "object",
                    "required": ["passed", "checks", "errors", "warnings"],
                },
            },
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
