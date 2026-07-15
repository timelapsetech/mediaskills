# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Check program-master runtime readiness: binaries, profile, OCR policy, pinned deps."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _mediaskills_common import emit_error, emit_success

SKILL_DIR = Path(__file__).resolve().parents[1]
OP = "program_master.doctor"
EXPECTED_PINS = {"timecode==1.5.1", "reportlab==5.0.0", "pypdf==6.14.2"}


def command_version(command: str, *args: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        proc = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    return text.splitlines()[0] if text else None


def audit_dependencies(skill_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    dependencies: set[str] = set()
    unpinned: set[str] = set()
    scripts_dir = skill_dir / "scripts"
    for source in sorted(scripts_dir.glob("*.py")):
        if source.name.startswith("_"):
            continue
        text = source.read_text(encoding="utf-8")
        for block in re.findall(r"dependencies\s*=\s*\[([^]]*)]", text, flags=re.S):
            for dependency in re.findall(r"['\"]([^'\"]+)['\"]", block):
                dependencies.add(dependency)
                if "==" not in dependency:
                    unpinned.add(dependency)
    if unpinned:
        errors.append(f"Python script dependencies must use exact pins: {sorted(unpinned)}")
    missing_pins = sorted(EXPECTED_PINS - dependencies)
    if missing_pins:
        errors.append(f"required pinned dependencies are not declared: {missing_pins}")
    return {
        "passed": not errors,
        "errors": errors,
        "details": {"declared_dependencies": sorted(dependencies)},
    }


def audit_runtime(skill_dir: Path = SKILL_DIR, profile_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    profile_source = (profile_path or skill_dir / "profiles" / "broadcast-default.json").resolve()
    try:
        profile = json.loads(profile_source.read_text(encoding="utf-8"))
        if str(profile.get("profile_version")) != "1.0":
            errors.append("default profile has an unsupported profile_version")
    except (OSError, json.JSONDecodeError) as exc:
        profile = {}
        errors.append(f"unable to read selected profile: {exc}")

    python_ok = sys.version_info >= (3, 11)
    if not python_ok:
        errors.append("Python 3.11 or newer is required")
    versions = {
        "python": platform.python_version(),
        "uv": command_version("uv", "--version"),
        "ffmpeg": command_version("ffmpeg", "-version"),
        "ffprobe": command_version("ffprobe", "-version"),
        "tesseract": command_version("tesseract", "--version"),
    }
    for required in ("uv", "ffmpeg", "ffprobe"):
        if not versions[required]:
            errors.append(f"required executable is unavailable or unusable: {required}")

    ocr = profile.get("ocr") or {}
    ocr_mode = str(ocr.get("mode", "optional"))
    ocr_language = str(ocr.get("language", "eng"))
    languages: list[str] = []
    if versions["tesseract"]:
        try:
            proc = subprocess.run(
                [shutil.which("tesseract") or "tesseract", "--list-langs"],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
            languages = [line.strip() for line in proc.stdout.splitlines()[1:] if line.strip()]
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            warnings.append("Tesseract is present but installed languages could not be listed")
    if ocr_mode == "required" and not versions["tesseract"]:
        errors.append("the selected profile requires Tesseract, but it is unavailable")
    elif ocr_mode == "optional" and not versions["tesseract"]:
        warnings.append("Tesseract is unavailable; optional slate OCR will be skipped")
    if ocr_mode != "off" and versions["tesseract"] and languages and ocr_language not in languages:
        message = f"Tesseract language {ocr_language!r} is not installed"
        (errors if ocr_mode == "required" else warnings).append(message)

    temp_ok = False
    try:
        with tempfile.TemporaryDirectory(prefix="program-master-doctor-") as directory:
            probe = Path(directory) / "write-test"
            probe.write_text("ok", encoding="utf-8")
            temp_ok = probe.read_text(encoding="utf-8") == "ok"
    except OSError as exc:
        errors.append(f"temporary workspace is not writable: {exc}")

    return {
        "passed": not errors,
        "checks": {
            "python_3_11_or_newer": python_ok,
            "uv_available": bool(versions["uv"]),
            "ffmpeg_available": bool(versions["ffmpeg"]),
            "ffprobe_available": bool(versions["ffprobe"]),
            "ocr_policy_satisfied": not any("Tesseract" in error for error in errors),
            "temporary_workspace_writable": temp_ok,
        },
        "errors": errors,
        "warnings": warnings,
        "details": {
            "profile": str(profile_source),
            "ocr_mode": ocr_mode,
            "ocr_language": ocr_language,
            "tesseract_languages": languages,
            "versions": versions,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Profile whose OCR policy should be checked")
    parser.add_argument("--json-output", help="Optional path for the complete audit JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    dependencies = audit_dependencies(SKILL_DIR)
    runtime = audit_runtime(
        SKILL_DIR,
        Path(args.profile).expanduser() if args.profile else None,
    )
    errors = list(dependencies["errors"]) + list(runtime["errors"])
    warnings = list(runtime["warnings"])
    result = {
        "schema_version": "1.0",
        "passed": not errors,
        "dependencies": dependencies,
        "runtime": runtime,
        "errors": errors,
        "warnings": warnings,
    }
    outputs: list[str] = []
    if args.json_output:
        output = Path(args.json_output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["output_path"] = str(output)
        outputs.append(str(output))
    if errors:
        emit_error(OP, "; ".join(errors), code=3)
    emit_success(OP, result, outputs)


if __name__ == "__main__":
    main()
