#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Syncing vendored shared libraries"
python3 scripts/sync_shared_libs.py

echo "==> Validating skills (agentskills)"
if command -v agentskills >/dev/null 2>&1; then
  python3 scripts/validate_all.py
elif command -v skills-ref >/dev/null 2>&1; then
  python3 scripts/validate_all.py
else
  echo "agentskills not found; using uv..."
  uv sync
  uv run python scripts/validate_all.py
fi

echo "==> Checking vendored library sync"
python3 scripts/sync_shared_libs.py --check

echo "==> Checking skills index.json"
python3 scripts/list_ops.py --check

echo "==> Running pytest"
if command -v uv >/dev/null 2>&1; then
  uv run pytest
else
  python3 -m pytest
fi

echo "All checks passed."
