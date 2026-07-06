# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Return captions-compliance skill capabilities and requirements."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_success, main_wrapper


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run info.py",
    )


def main() -> None:
    build_parser().parse_args()
    emit_success(
        "caption.info",
        {
            "binaries": ["ffmpeg"],
            "pep723": ["faster-whisper (to-captions-pipeline.py only)"],
            "exports": ["SRT cleanup", "CEA-608 SCC", "SMPTE-TT / TTML"],
            "compliance": "FCC-oriented heuristics; not legal certification",
            "scripts": [
                "rules.py",
                "validate.py",
                "format.py",
                "to-scc.py",
                "to-smpte-tt.py",
                "apply-busy-zones.py",
                "to-captions-pipeline.py",
            ],
            "references": ["references/BROADCAST_GUIDELINES.md"],
        },
    )


if __name__ == "__main__":
    main_wrapper(main)
