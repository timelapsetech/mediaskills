#!/usr/bin/env bash
set -euo pipefail
OP_ID="install-media-tools.which"
source "$(dirname "$0")/_mediaskills_common.sh"
parse_args "$@"

TOOL="$(json_get_required tool)"
PATH_VAL="$(command -v "$TOOL" 2>/dev/null || true)"
DATA=$(python3 -c "import json,sys; print(json.dumps({'tool': sys.argv[1], 'path': sys.argv[2] or None}))" "$TOOL" "$PATH_VAL")
emit_success "install-media-tools.which" "$DATA" "[]"
