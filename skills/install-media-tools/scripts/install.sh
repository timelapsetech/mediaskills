#!/usr/bin/env bash
set -euo pipefail
OP_ID="install-media-tools.install"
source "$(dirname "$0")/_mediaskills_common.sh"
parse_args "$@"

ACTIONS=()
PLATFORM="$(uname -s)"

install_with_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    ACTIONS+=("skipped_brew: Homebrew not found")
    return
  fi
  emit_progress "brew_install" 20
  if brew install ffmpeg imagemagick exiftool tesseract yt-dlp uv 2>/dev/null; then
    ACTIONS+=("brew_install: ok")
  else
    ACTIONS+=("brew_install: attempted (some packages may have failed)")
  fi
}

install_with_apt() {
  if ! command -v apt-get >/dev/null 2>&1; then
    ACTIONS+=("skipped_apt: apt-get not found")
    return
  fi
  emit_progress "apt_install" 20
  if command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
  else
    SUDO=()
  fi
  if "${SUDO[@]}" apt-get update -qq 2>/dev/null && \
     "${SUDO[@]}" apt-get install -y -qq ffmpeg imagemagick libimage-exiftool-perl tesseract-ocr 2>/dev/null; then
    ACTIONS+=("apt_install: ok")
  else
    ACTIONS+=("apt_install: attempted (may require sudo)")
  fi
}

install_yt_dlp() {
  if command -v yt-dlp >/dev/null 2>&1; then
    ACTIONS+=("yt-dlp: already present")
    return
  fi
  emit_progress "yt_dlp" 60
  if command -v apt-get >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
      sudo apt-get install -y -qq yt-dlp 2>/dev/null && ACTIONS+=("yt-dlp: apt") && return
    fi
  fi
  local dest="${HOME}/.local/bin/yt-dlp"
  mkdir -p "$(dirname "$dest")"
  if curl -fsSL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o "$dest" 2>/dev/null; then
    chmod a+rx "$dest"
    ACTIONS+=("yt-dlp: installed to ${dest}")
  else
    ACTIONS+=("yt-dlp: install failed")
  fi
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    ACTIONS+=("uv: already present")
    return
  fi
  emit_progress "uv" 80
  if curl -fsSL https://astral.sh/uv/install.sh | sh 2>/dev/null; then
    ACTIONS+=("uv: installed via astral.sh")
  else
    ACTIONS+=("uv: install failed")
  fi
}

emit_progress "checking" 10
case "$PLATFORM" in
  Darwin)
    install_with_brew
    ;;
  Linux)
    if [[ -f /etc/debian_version ]]; then
      install_with_apt
    elif command -v brew >/dev/null 2>&1; then
      install_with_brew
    else
      ACTIONS+=("skipped: unsupported Linux distro (manual install required)")
    fi
    install_yt_dlp
    install_uv
    ;;
  *)
    ACTIONS+=("skipped: platform ${PLATFORM} not supported by auto-install")
    ;;
esac

emit_progress "done" 100
if ((${#ACTIONS[@]})); then
  ACTIONS_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${ACTIONS[@]}")
else
  ACTIONS_JSON="[]"
fi
DATA=$(python3 -c "import json,sys; print(json.dumps({'platform': sys.argv[1], 'actions': json.loads(sys.argv[2])}))" "$PLATFORM" "$ACTIONS_JSON")
emit_success "install-media-tools.install" "$DATA" "[]"
