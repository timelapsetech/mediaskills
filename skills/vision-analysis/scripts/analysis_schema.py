# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Return the JSON schema for frame analysis documents."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_success, main_wrapper

OP = "vision.analysis_schema"


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=__doc__)


def main() -> None:
    build_parser().parse_args()
    emit_success(
        OP,
        {
            "type": "object",
            "description": "Frame analysis document produced by agent vision + merge_analysis.py",
            "properties": {
                "manifest_path": {"type": "string"},
                "input_path": {"type": "string"},
                "frame_count": {"type": "number"},
                "analyzed_count": {"type": "number"},
                "frames": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "shot_index": {"type": "number"},
                            "start_seconds": {"type": "number"},
                            "end_seconds": {"type": "number"},
                            "start_timecode": {"type": "string"},
                            "end_timecode": {"type": "string"},
                            "frame_path": {"type": "string"},
                            "description": {"type": "string"},
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "on_screen_text": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "text": {"type": "string"},
                                        "text_type": {
                                            "type": "string",
                                            "enum": [
                                                "title",
                                                "lower_third",
                                                "subtitle",
                                                "locator",
                                                "graphic",
                                                "background_text",
                                                "credit",
                                                "other",
                                            ],
                                        },
                                        "location": {
                                            "type": "string",
                                            "enum": [
                                                "top",
                                                "bottom",
                                                "left",
                                                "right",
                                                "center",
                                                "full_screen",
                                                "unknown",
                                            ],
                                        },
                                        "confidence": {"type": "number"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
