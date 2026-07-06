#!/usr/bin/env bash
set -euo pipefail
OP_ID="install-media-tools.doctor"
source "$(dirname "$0")/_mediaskills_common.sh"
parse_args "$@"

TOOLS="ffmpeg ffprobe convert exiftool tesseract yt-dlp uv"
INSTALLED=()
MISSING=()
for t in $TOOLS; do
  if command -v "$t" >/dev/null 2>&1; then
    INSTALLED+=("$t")
  else
    MISSING+=("$t")
  fi
done

PLATFORM="$(uname -s | tr '[:upper:]' '[:lower:]')"
MISSING_CSV="$( (IFS=,; echo "${MISSING[*]:-}") )"
INSTALLED_CSV="$( (IFS=,; echo "${INSTALLED[*]:-}") )"
DATA=$(python3 -c "
import json, sys
missing = [x for x in sys.argv[1].split(',') if x]
installed = [x for x in sys.argv[2].split(',') if x]
print(json.dumps({
    'healthy': len(missing) == 0,
    'installed': installed,
    'missing': missing,
    'platform': sys.argv[3],
}))
" "$MISSING_CSV" "$INSTALLED_CSV" "$PLATFORM")
emit_success "install-media-tools.doctor" "$DATA" "[]"
