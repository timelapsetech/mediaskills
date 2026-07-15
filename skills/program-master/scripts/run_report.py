# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf==6.14.2", "reportlab==5.0.0", "timecode==1.5.1"]
# ///

"""Run segmentation, Markdown/JSON/PDF compilation, and fail-closed QC in one command."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import shutil
from pathlib import Path

from _mediaskills_common import emit_error, emit_progress, emit_success, main_wrapper
from _profile_lib import load_profile

OP = "program_master.run_report"
SCRIPTS = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "-i", required=True, help="Source broadcast master")
    parser.add_argument("--output-dir", required=True, help="Stable output bundle directory")
    parser.add_argument("--profile", help="Versioned JSON run profile")
    parser.add_argument("--label-overrides", help="Optional refined labels by segment index")
    parser.add_argument("--video-stream", type=int, default=None)
    parser.add_argument("--audio-stream", type=int, default=None)
    parser.add_argument("--audio-policy", choices=["single", "all"], default=None)
    parser.add_argument("--timecode-mode", choices=["embedded", "file"], default=None)
    parser.add_argument(
        "--require-embedded-timecode",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--ocr-mode", choices=["off", "optional", "required"], default=None)
    parser.add_argument("--ocr-lang", default=None)
    parser.add_argument("--ocr-psm", type=int, default=None)
    parser.add_argument(
        "--verify-source-hash",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recompute the source hash during final validation (default on)",
    )
    return parser


def run_stage(name: str, command: list[str]) -> dict:
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"{name} failed").strip()
        raise RuntimeError(f"{name} failed: {detail[-1600:]}")
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{name} produced no machine-readable result")
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} result was not valid JSON") from exc
    if not result.get("ok"):
        raise RuntimeError(f"{name} reported failure: {result.get('error')}")
    return result


def optional_flag(command: list[str], flag: str, value: object | None) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def main() -> None:
    args = build_parser().parse_args()
    source = Path(args.input).expanduser().resolve()
    if not source.is_file():
        emit_error(OP, f"Input not found: {source}", code=1)
    label_overrides = (
        str(Path(args.label_overrides).expanduser().resolve()) if args.label_overrides else None
    )
    if label_overrides and not Path(label_overrides).is_file():
        emit_error(OP, f"Label override file not found: {label_overrides}", code=1)
    profile, profile_path = load_profile(args.profile)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = source.stem
    manifest_path = output_dir / f"{stem}_labeled_segments.json"
    probes_dir = output_dir / f"{stem}_segment_probes"
    markdown_path = output_dir / f"{stem}_program_master.md"
    report_json_path = output_dir / f"{stem}_program_master_report.json"
    pdf_path = output_dir / f"{stem}_broadcast_segment_report.pdf"
    thumbnail_json_path = output_dir / f"{stem}_broadcast_segment_report.json"
    qc_path = output_dir / f"{stem}_qc.json"
    run_path = output_dir / f"{stem}_run.json"
    thumbnail_dir = output_dir / f"{pdf_path.stem}_thumbnails"

    # Stable output names are intentional. Remove only this workflow's known prior
    # derivatives so a rerun cannot leave stale probe or thumbnail evidence behind.
    for stale_dir in (probes_dir, thumbnail_dir):
        if stale_dir.is_dir():
            shutil.rmtree(stale_dir)
    for stale_file in (
        manifest_path,
        markdown_path,
        report_json_path,
        pdf_path,
        thumbnail_json_path,
        qc_path,
        run_path,
    ):
        if stale_file.is_file():
            stale_file.unlink()

    emit_progress("labeling segments", 10)
    label_command = [
        sys.executable,
        str(SCRIPTS / "label_segments.py"),
        "--input",
        str(source),
        "--output",
        str(manifest_path),
        "--frames-dir",
        str(probes_dir),
        "--profile",
        str(profile_path),
    ]
    optional_flag(label_command, "--video-stream", args.video_stream)
    optional_flag(label_command, "--audio-stream", args.audio_stream)
    optional_flag(label_command, "--audio-policy", args.audio_policy)
    optional_flag(label_command, "--timecode-mode", args.timecode_mode)
    optional_flag(label_command, "--ocr-mode", args.ocr_mode)
    optional_flag(label_command, "--ocr-lang", args.ocr_lang)
    optional_flag(label_command, "--ocr-psm", args.ocr_psm)
    if args.require_embedded_timecode is True:
        label_command.append("--require-embedded-timecode")
    elif args.require_embedded_timecode is False:
        label_command.append("--no-require-embedded-timecode")
    label_result = run_stage("label_segments", label_command)

    emit_progress("compiling Markdown and JSON", 50)
    compile_command = [
        sys.executable,
        str(SCRIPTS / "compile.py"),
        "--structure-path",
        str(manifest_path),
        "--output",
        str(markdown_path),
        "--json-output",
        str(report_json_path),
        "--profile",
        str(profile_path),
    ]
    if label_overrides:
        compile_command.extend(["--label-overrides", label_overrides])
    compile_result = run_stage("compile", compile_command)

    emit_progress("compiling thumbnail PDF", 65)
    pdf_command = [
        sys.executable,
        str(SCRIPTS / "compile_pdf.py"),
        "--structure-path",
        str(manifest_path),
        "--output",
        str(pdf_path),
        "--json-output",
        str(thumbnail_json_path),
        "--profile",
        str(profile_path),
        "--deterministic",
    ]
    if label_overrides:
        pdf_command.extend(["--label-overrides", label_overrides])
    pdf_result = run_stage("compile_pdf", pdf_command)

    emit_progress("validating bundle", 90)
    validate_command = [
        sys.executable,
        str(SCRIPTS / "validate_report.py"),
        "--manifest",
        str(manifest_path),
        "--report-json",
        str(report_json_path),
        "--thumbnail-report-json",
        str(thumbnail_json_path),
        "--pdf",
        str(pdf_path),
        "--output",
        str(qc_path),
        "--profile",
        str(profile_path),
    ]
    if not args.verify_source_hash:
        validate_command.append("--no-verify-source-hash")
    qc_result = run_stage("validate_report", validate_command)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_record = {
        "schema_version": "2.0",
        "passed": True,
        "source": manifest.get("provenance", {}).get("source"),
        "profile": manifest.get("provenance", {}).get("profile"),
        "effective_config": manifest.get("effective_config"),
        "label_overrides": (
            (json.loads(report_json_path.read_text(encoding="utf-8")).get("generation") or {}).get(
                "label_overrides"
            )
        ),
        "artifacts": {
            "manifest": str(manifest_path),
            "markdown": str(markdown_path),
            "report_json": str(report_json_path),
            "pdf": str(pdf_path),
            "thumbnail_report_json": str(thumbnail_json_path),
            "qc": str(qc_path),
            "probes_dir": str(probes_dir),
            "thumbnails_dir": pdf_result["data"].get("thumbnail_dir"),
        },
        "stage_results": {
            "label_segments": label_result["op"],
            "compile": compile_result["op"],
            "compile_pdf": pdf_result["op"],
            "validate_report": qc_result["op"],
        },
    }
    run_path.write_text(json.dumps(run_record, indent=2) + "\n", encoding="utf-8")
    emit_progress("done", 100)
    outputs = [
        str(manifest_path),
        str(markdown_path),
        str(report_json_path),
        str(pdf_path),
        str(thumbnail_json_path),
        str(qc_path),
        str(run_path),
    ]
    emit_success(
        OP,
        {"passed": True, "output_dir": str(output_dir), "artifacts": run_record["artifacts"]},
        outputs,
    )


if __name__ == "__main__":
    main_wrapper(main)
