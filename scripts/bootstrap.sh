#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> uv sync (dev dependencies)"
uv sync

echo "==> Sync shared libraries into skills"
uv run python scripts/sync_shared_libs.py

echo "==> Doctor (system binaries)"
if [[ -x skills/install-media-tools/scripts/doctor.sh ]]; then
  bash skills/install-media-tools/scripts/doctor.sh || true
else
  echo "(install-media-tools not yet present — skipping doctor)"
fi

echo "Bootstrap complete. Run: ./scripts/smoke.sh"
