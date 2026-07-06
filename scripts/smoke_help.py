#!/usr/bin/env python3
"""Run --help (or syntax/minimal smoke) on every public CLI script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"

BASH_SMOKE: dict[str, list[str] | None] = {
    "doctor.sh": [],
    "detect-tools.sh": [],
    "which.sh": ["--tool", "ffmpeg"],
    "install.sh": None,
}


def run_cmd(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def discover_python_scripts() -> list[Path]:
    scripts: list[Path] = []
    for skill_dir in sorted(SKILLS_ROOT.iterdir()):
        script_dir = skill_dir / "scripts"
        if not script_dir.is_dir():
            continue
        for path in sorted(script_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            scripts.append(path)
    return scripts


def discover_bash_scripts() -> list[Path]:
    script_dir = SKILLS_ROOT / "install-media-tools" / "scripts"
    if not script_dir.is_dir():
        return []
    return sorted(p for p in script_dir.glob("*.sh") if not p.name.startswith("_"))


def test_python_help(script: Path) -> tuple[bool, str]:
    if Path("/usr/bin/uv").exists() or subprocess.run(["which", "uv"], capture_output=True).returncode == 0:
        cmd = ["uv", "run", str(script), "--help"]
    else:
        cmd = [sys.executable, str(script), "--help"]
    result = run_cmd(cmd, cwd=script.parent)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error").strip()[:300]
        return False, err
    if "--help" not in result.stdout and "usage:" not in result.stdout.lower():
        return False, "no help text in stdout"
    return True, "ok"


def test_bash_script(script: Path) -> tuple[bool, str]:
    syntax = run_cmd(["bash", "-n", str(script)])
    if syntax.returncode != 0:
        return False, (syntax.stderr or "bash -n failed").strip()[:300]

    extra = BASH_SMOKE.get(script.name)
    if extra is None:
        return True, "syntax ok"

    result = run_cmd(["bash", str(script), *extra], cwd=script.parent)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "run failed").strip()[:300]
        return False, err
    return True, "ok"


def main() -> int:
    failures: list[str] = []
    passed = 0

    print("Python scripts (--help):")
    for script in discover_python_scripts():
        ok, detail = test_python_help(script)
        rel = script.relative_to(REPO_ROOT)
        if ok:
            print(f"  OK  {rel}")
            passed += 1
        else:
            print(f"  FAIL {rel}: {detail}")
            failures.append(str(rel))

    print("\nBash scripts (syntax + minimal run):")
    for script in discover_bash_scripts():
        ok, detail = test_bash_script(script)
        rel = script.relative_to(REPO_ROOT)
        if ok:
            print(f"  OK  {rel} ({detail})")
            passed += 1
        else:
            print(f"  FAIL {rel}: {detail}")
            failures.append(str(rel))

    total = passed + len(failures)
    print(f"\n{passed}/{total} CLI entry points passed smoke help.")
    if failures:
        print("Failures:", ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
