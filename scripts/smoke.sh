#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FULL=false
WHISPER=false
INSTALL=false
SELF_TEST=false

for arg in "$@"; do
  case "$arg" in
    --full) FULL=true ;;
    --whisper) WHISPER=true ;;
    --install) INSTALL=true ;;
    --self-test) SELF_TEST=true ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/smoke.sh [--full] [--whisper] [--install] [--self-test]

Local publish validation gate (run from repo root).
Quality is enforced locally — GitHub Actions only deploys the doc site.

  (default)    doctor + check.sh (validate, sync, pytest)
  --full       also run --help smoke on every CLI script
  --whisper    also run speech-captions Whisper integration tests
  --install    also run install-media-tools install.sh (may invoke brew/apt)
  --self-test  also run program-master (and forced-narrative if present) golden self-tests

First time: ./scripts/bootstrap.sh
Recommended: ./scripts/install-git-hooks.sh  # pre-push runs this smoke gate
EOF
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

if command -v uv >/dev/null 2>&1; then
  echo "==> uv sync"
  uv sync
  PY=(uv run python)
  PYTEST=(uv run pytest)
else
  echo "WARNING: uv not found; using system python" >&2
  PY=(python3)
  PYTEST=(python3 -m pytest)
fi

echo "==> Doctor (binary health)"
DOCTOR_JSON="$(bash skills/install-media-tools/scripts/doctor.sh)"
echo "$DOCTOR_JSON" | tail -1

MISSING="$(echo "$DOCTOR_JSON" | tail -1 | "${PY[@]}" -c "
import json, sys
d = json.loads(sys.stdin.read())
print(','.join(d.get('data', {}).get('missing', [])))
")"

CORE_MISSING="$(echo "$MISSING" | tr ',' '\n' | grep -E '^(ffmpeg|ffprobe|uv)$' || true)"
if [[ -n "$CORE_MISSING" ]]; then
  echo "ERROR: Missing required tools: $(echo "$CORE_MISSING" | tr '\n' ' ')" >&2
  echo "Install via: bash skills/install-media-tools/scripts/install.sh" >&2
  exit 1
fi

OPTIONAL_MISSING="$(echo "$MISSING" | tr ',' '\n' | grep -Ev '^(ffmpeg|ffprobe|uv)$' | grep -v '^$' || true)"
if [[ -n "$OPTIONAL_MISSING" ]]; then
  echo "NOTE: Optional tools not on PATH (some tests may skip):"
  echo "$OPTIONAL_MISSING" | sed 's/^/  - /'
fi

echo "==> Core checks (validate + sync + pytest)"
./scripts/check.sh

if [[ "$FULL" == true ]]; then
  echo "==> CLI --help smoke"
  "${PY[@]}" scripts/smoke_help.py
fi

if [[ "$WHISPER" == true ]]; then
  echo "==> Whisper integration tests"
  MEDIASKILLS_RUN_WHISPER=1 "${PYTEST[@]}" skills/speech-captions/tests/
fi

if [[ "$INSTALL" == true ]]; then
  echo "==> install-media-tools install.sh"
  INSTALL_JSON="$(bash skills/install-media-tools/scripts/install.sh)"
  echo "$INSTALL_JSON" | tail -1
  echo "$INSTALL_JSON" | tail -1 | "${PY[@]}" -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d.get('ok'), d
assert d.get('op') == 'install-media-tools.install', d
print('install.sh OK')
"
fi

if [[ "$SELF_TEST" == true ]]; then
  WORK="$(mktemp -d "${TMPDIR:-/tmp}/mediaskills-self-test.XXXXXX")"
  echo "==> program-master self_test (work-dir: $WORK/pm)"
  (
    cd skills/program-master
    uv run scripts/self_test.py --work-dir "$WORK/pm"
  )
  if [[ -f skills/forced-narrative-exact/scripts/self_test.py ]]; then
    echo "==> forced-narrative-exact self_test (work-dir: $WORK/fne)"
    (
      cd skills/forced-narrative-exact
      uv run scripts/self_test.py --work-dir "$WORK/fne"
    )
  fi
  rm -rf "$WORK"
fi

SKILL_COUNT="$(find skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')"
echo ""
echo "Smoke passed: ${SKILL_COUNT} skills, core tools OK."
if [[ "$FULL" == true ]]; then
  echo "  --full: all CLI --help checks passed"
fi
if [[ "$WHISPER" == true ]]; then
  echo "  --whisper: speech-captions integration tests passed"
fi
if [[ "$INSTALL" == true ]]; then
  echo "  --install: install.sh smoke passed"
fi
if [[ "$SELF_TEST" == true ]]; then
  echo "  --self-test: golden skill self-tests passed"
fi
