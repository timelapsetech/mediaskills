#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
chmod +x .githooks/pre-push
git config core.hooksPath .githooks
echo "Installed git hooks from .githooks/ (core.hooksPath=.githooks)"
echo "pre-push will run: ./scripts/smoke.sh"
