#!/usr/bin/env python3
"""Validate all skills against the agentskills.io spec via skills-ref."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"


def validate_cmd() -> list[str]:
    """Resolve the skills validator CLI (skills-ref or agentskills from pip package)."""
    import shutil

    for candidate in ("skills-ref", "agentskills"):
        if shutil.which(candidate):
            return [candidate]
    # Fall back to uv-run agentskills from project venv
    return ["uv", "run", "agentskills"]


def main() -> int:
    if not SKILLS_ROOT.is_dir():
        print("No skills/ directory found.", file=sys.stderr)
        return 1

    failures: list[str] = []
    skills = sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if not skills:
        print("No skills found.", file=sys.stderr)
        return 1

    cmd = validate_cmd()
    for skill in skills:
        result = subprocess.run(
            [*cmd, "validate", str(skill)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failures.append(skill.name)
            print(result.stdout or result.stderr, file=sys.stderr)
        else:
            print(f"OK  {skill.name}")

    if failures:
        print(f"\n{len(failures)} skill(s) failed validation.", file=sys.stderr)
        return 1

    print(f"\nAll {len(skills)} skills passed agentskills validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
