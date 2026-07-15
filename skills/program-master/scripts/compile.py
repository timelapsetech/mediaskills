# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Compile a labeled segment manifest into agent-ready Markdown and JSON reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import (
    add_output_arg,
    emit_error,
    emit_success,
    main_wrapper,
    resolve_output,
)
from _report_lib import build_report, render_markdown_report
from _profile_lib import (
    effective_label_overrides,
    label_override_provenance,
    load_profile,
    validate_label_overrides,
)
from _validation_lib import effective_validation_policy, validate_manifest

OP = "program_master.compile"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run compile.py --structure-path labeled_segments.json",
    )
    add_output_arg(parser)
    parser.add_argument(
        "--structure-path",
        "--manifest-path",
        dest="structure_path",
        required=True,
        help="Path to labeled segment JSON from label_segments.py",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path for compiled report JSON (default: auto-generated)",
    )
    parser.add_argument("--profile", help="Versioned JSON run profile")
    parser.add_argument("--label-overrides", help="Optional refined labels by segment index")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    structure_path = args.structure_path
    if not structure_path or not Path(structure_path).is_file():
        emit_error(OP, "Provide --structure-path from label_segments.py or analyze_structure.py", code=1)

    manifest = json.loads(Path(structure_path).read_text(encoding="utf-8"))
    profile, profile_path = load_profile(args.profile)
    require_embedded, min_gaps = effective_validation_policy(manifest, profile)
    validation = validate_manifest(
        manifest,
        require_embedded_timecode=require_embedded,
        min_gaps=min_gaps,
    )
    if not validation["passed"]:
        emit_error(OP, "; ".join(validation["errors"]), code=3)
    source = manifest.get("input_path") or "program"
    labels = profile.get("labels") or {}
    overrides = effective_label_overrides(profile, args.label_overrides)
    validate_label_overrides(
        manifest,
        overrides,
        require_content=bool(labels.get("require_overrides_for_content", False)),
    )
    report = build_report(
        manifest,
        label_mode=str(labels.get("mode", "generic")),
        label_overrides=overrides,
    )
    report["validation"] = validation
    report["generation"] = {
        "profile_path": str(profile_path),
        "label_overrides": label_override_provenance(args.label_overrides),
    }

    md = resolve_output(source, "_program_master.md", args.output)
    md.write_text(render_markdown_report(report), encoding="utf-8")

    out_json = resolve_output(source, "_program_master_report.json", args.json_output)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    emit_success(
        OP,
        {
            "output_path": str(md),
            "json_path": str(out_json),
            "segment_count": report.get("segment_count"),
            "rows": report.get("rows"),
            "episode": report.get("episode"),
        },
        [str(md), str(out_json)],
    )


if __name__ == "__main__":
    main_wrapper(main)
