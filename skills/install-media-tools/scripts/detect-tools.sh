#!/usr/bin/env bash
set -euo pipefail
OP_ID="install-media-tools.detect_tools"
source "$(dirname "$0")/_mediaskills_common.sh"
parse_args "$@"

TOOLS="ffmpeg ffprobe convert exiftool tesseract yt-dlp uv"
FOUND=()
for t in $TOOLS; do
  command -v "$t" >/dev/null 2>&1 && FOUND+=("$t")
done
FOUND_CSV="$( (IFS=,; echo "${FOUND[*]:-}") )"
DATA=$(python3 -c "import json,sys; print(json.dumps({'tools': [x for x in sys.argv[1].split(',') if x]}))" "$FOUND_CSV")
emit_success "install-media-tools.detect_tools" "$DATA" "[]"
