#!/usr/bin/env bash
# Shared helpers for install-media-tools bash scripts.
set -euo pipefail

parse_args() {
  ARGS_JSON="{}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --args)
        ARGS_JSON="${2:-"{}"}"
        shift 2
        ;;
      --tool)
        TOOL="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
}

json_get() {
  local key="$1"
  python3 -c "import json,sys; d=json.loads(sys.argv[1]); v=d.get(sys.argv[2]); print('' if v is None else v)" "$ARGS_JSON" "$key" 2>/dev/null || echo ""
}

json_get_required() {
  local key="$1"
  local val
  val="$(json_get "$key")"
  if [[ -z "$val" ]]; then
    if [[ "$key" == "tool" && -n "${TOOL:-}" ]]; then
      echo "$TOOL"
      return
    fi
    emit_error "${OP_ID:-unknown}" "Missing required arg: ${key}"
  fi
  echo "$val"
}

emit_progress() {
  local stage="$1"
  local pct="$2"
  echo "{\"progress\": ${pct}, \"stage\": \"${stage}\"}" >&2
}

emit_success() {
  local op="$1"
  local data="$2"
  local outputs="${3:-[]}"
  python3 -c "
import json, sys
op, data_s, outputs_s = sys.argv[1:4]
try:
    data = json.loads(data_s) if data_s else {}
except json.JSONDecodeError:
    data = {'raw': data_s}
try:
    outputs = json.loads(outputs_s) if outputs_s else []
except json.JSONDecodeError:
    outputs = [outputs_s] if outputs_s else []
print(json.dumps({'ok': True, 'op': op, 'data': data, 'output_paths': outputs}))
" "$op" "$data" "$outputs"
}

emit_error() {
  local op="$1"
  local err="$2"
  python3 -c "import json,sys; print(json.dumps({'ok': False, 'op': sys.argv[1], 'error': sys.argv[2]}))" "$op" "$err" >&2
  exit 3
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    emit_error "${OP_ID:-unknown}" "${cmd} not found. Run install-media-tools doctor or install scripts."
  fi
}
