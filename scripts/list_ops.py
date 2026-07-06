#!/usr/bin/env python3
"""Discover skills, scripts, and op IDs; emit or write skills/index.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
VERSION = "0.1.0"

OP_RE = re.compile(r"""op\s*=\s*["']([^"']+)["']|OP\s*=\s*["']([^"']+)["']""")
PEP723_DEPS_RE = re.compile(r"dependencies\s*=\s*\[(.*?)\]", re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
METADATA_BLOCK_RE = re.compile(r"metadata:\n((?:  .+\n)+)")


def parse_frontmatter(skill_md: Path) -> dict[str, object]:
    text = skill_md.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)
    info: dict[str, object] = {}
    for line in block.splitlines():
        if line.startswith("  ") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"')
        if key == "metadata":
            continue
        info[key] = value
    meta_match = METADATA_BLOCK_RE.search(block)
    if meta_match:
        meta: dict[str, str] = {}
        for line in meta_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.strip().partition(":")
                meta[k.strip()] = v.strip()
        info["metadata"] = meta
    return info


def parse_pep723_deps(script: Path) -> list[str]:
    text = script.read_text(encoding="utf-8")
    if "# /// script" not in text:
        return []
    match = PEP723_DEPS_RE.search(text)
    if not match:
        return []
    inner = match.group(1)
    return [p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()]


def parse_op(script: Path) -> str | None:
    for line in script.read_text(encoding="utf-8").splitlines():
        m = OP_RE.search(line)
        if m:
            return m.group(1) or m.group(2)
    return None


def parse_epilog_flags(script: Path) -> list[str]:
    text = script.read_text(encoding="utf-8")
    flags: list[str] = []
    for token in ("--input", "--output", "--url", "--timecode", "--fps"):
        if token in text:
            flags.append(token)
    return flags


def discover_bash_scripts(skill_dir: Path) -> list[dict[str, object]]:
    script_dir = skill_dir / "scripts"
    if not script_dir.is_dir():
        return []
    entries: list[dict[str, object]] = []
    for path in sorted(script_dir.glob("*.sh")):
        if path.name.startswith("_"):
            continue
        op = f"install-media-tools.{path.stem.replace('-', '_')}"
        entries.append(
            {
                "script": path.name,
                "language": "bash",
                "op": op,
                "pep723_dependencies": [],
            }
        )
    return entries


def discover_skill(skill_dir: Path) -> dict[str, object] | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    meta = parse_frontmatter(skill_md)
    name = str(meta.get("name") or skill_dir.name)
    scripts: list[dict[str, object]] = []
    script_dir = skill_dir / "scripts"
    if script_dir.is_dir():
        for path in sorted(script_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            op = parse_op(path)
            scripts.append(
                {
                    "script": path.name,
                    "language": "python",
                    "op": op,
                    "pep723_dependencies": parse_pep723_deps(path),
                    "common_flags": parse_epilog_flags(path),
                }
            )
    if name == "install-media-tools":
        scripts.extend(discover_bash_scripts(skill_dir))
    return {
        "name": name,
        "description": meta.get("description", ""),
        "license": meta.get("license", "MIT"),
        "compatibility": meta.get("compatibility", ""),
        "metadata": meta.get("metadata", {}),
        "scripts": scripts,
    }


def build_index() -> dict[str, object]:
    skills = []
    for path in sorted(SKILLS_ROOT.iterdir()):
        if not path.is_dir():
            continue
        skill = discover_skill(path)
        if skill:
            skills.append(skill)
    return {
        "version": VERSION,
        "repository": "https://github.com/timelapsetech/mediaskills",
        "spec": "https://agentskills.io/specification",
        "skill_count": len(skills),
        "skills": skills,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        metavar="PATH",
        help="Write JSON index (default: skills/index.json)",
        nargs="?",
        const=str(SKILLS_ROOT / "index.json"),
    )
    parser.add_argument("--check", action="store_true", help="Exit 1 if index is stale")
    args = parser.parse_args()

    index = build_index()
    payload = json.dumps(index, indent=2) + "\n"

    if args.write:
        out = Path(args.write)
        out.write_text(payload, encoding="utf-8")
        print(f"Wrote {out} ({index['skill_count']} skills)")
        return 0

    if args.check:
        path = SKILLS_ROOT / "index.json"
        if not path.is_file():
            print("skills/index.json missing; run: python scripts/list_ops.py --write", file=sys.stderr)
            return 1
        if path.read_text(encoding="utf-8") != payload:
            print("skills/index.json is stale; run: python scripts/list_ops.py --write", file=sys.stderr)
            return 1
        print("skills/index.json is up to date.")
        return 0

    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
