#!/usr/bin/env python3
"""Copy canonical _shared helpers into each skill's scripts/ directory."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED = REPO_ROOT / "_shared"
CANONICAL_PY = SHARED / "media_skill_common.py"
CANONICAL_SH = SHARED / "common.sh"
TARGET_PY = "_mediaskills_common.py"
TARGET_SH = "_mediaskills_common.sh"


def skill_dirs() -> list[Path]:
    skills_root = REPO_ROOT / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(p for p in skills_root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def sync_skill(skill_dir: Path) -> list[str]:
    changes: list[str] = []
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return changes

    # Python skills get vendored common module
    if CANONICAL_PY.is_file():
        dest = scripts_dir / TARGET_PY
        if skill_dir.name != "install-media-tools":
            if not dest.exists() or dest.read_text() != CANONICAL_PY.read_text():
                shutil.copy2(CANONICAL_PY, dest)
                changes.append(str(dest))

    # install-media-tools uses bash common
    if skill_dir.name == "install-media-tools" and CANONICAL_SH.is_file():
        dest = scripts_dir / TARGET_SH
        if not dest.exists() or dest.read_text() != CANONICAL_SH.read_text():
            shutil.copy2(CANONICAL_SH, dest)
            changes.append(str(dest))

    return changes


def check_all() -> int:
    errors: list[str] = []
    for skill_dir in skill_dirs():
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            continue
        if skill_dir.name == "install-media-tools":
            dest = scripts_dir / TARGET_SH
            if not dest.is_file() or dest.read_text() != CANONICAL_SH.read_text():
                errors.append(f"Out of sync: {dest}")
        else:
            dest = scripts_dir / TARGET_PY
            if not dest.is_file() or dest.read_text() != CANONICAL_PY.read_text():
                errors.append(f"Out of sync: {dest}")
    if errors:
        print("Vendored shared libraries are out of sync. Run: python scripts/sync_shared_libs.py", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("All vendored shared libraries are in sync.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify sync without copying")
    args = parser.parse_args()

    if args.check:
        raise SystemExit(check_all())

    total: list[str] = []
    for skill_dir in skill_dirs():
        total.extend(sync_skill(skill_dir))
    if total:
        print(f"Synced {len(total)} file(s):")
        for path in total:
            print(f"  {path}")
    else:
        print("Nothing to sync.")


if __name__ == "__main__":
    main()
