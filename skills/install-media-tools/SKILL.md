---
name: install-media-tools
description: Detect, verify, and install media processing binaries (ffmpeg, ImageMagick, exiftool, tesseract, yt-dlp, uv) on macOS and Linux. Use before other mediaskills when doctor reports missing tools, when ffprobe/ffmpeg is not found, or when setting up a fresh dev machine or CI runner.
license: MIT
compatibility: Bash scripts only — no uv required. Uses python3 for JSON output (stdlib). install.sh may invoke brew or apt with elevated privileges on Linux.
metadata:
  mediaskills-category: setup
  mediaskills-binaries: ffmpeg ffprobe imagemagick convert exiftool tesseract yt-dlp uv
---

# Install media tools

Bootstrap the **system binaries** other mediaskills depend on. These scripts run in plain bash so they work **before** `uv` is installed.

## When to use

- **First setup** — run `doctor.sh` on a new machine or CI runner before using `inspect`, `audio`, `video-transformation`, etc.
- **Missing binary errors** — when another skill returns `ffmpeg not found` or exit code 2.
- **Path debugging** — use `which.sh` to confirm which binary the agent shell resolves.
- **Not for Python deps** — other skills use `uv run` with PEP 723 inline deps; this skill only installs OS-level tools.

## Toolchain overview

| Tool | Provided by | Used by |
| --- | --- | --- |
| `ffmpeg` / `ffprobe` | [ffmpeg](https://ffmpeg.org) package | inspect, audio, video-transformation, shots, speech-captions |
| `convert` / `magick` | [ImageMagick](https://imagemagick.org) | image, vision-analysis |
| `exiftool` | [ExifTool](https://exiftool.org) | image EXIF, metadata workflows |
| `tesseract` | [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | image OCR, vision-analysis |
| `yt-dlp` | [yt-dlp](https://github.com/yt-dlp/yt-dlp) | download skill |
| `uv` | [uv](https://docs.astral.sh/uv/) | running Python skill scripts |

`doctor.sh` checks for `ffmpeg`, `ffprobe`, `convert` (ImageMagick CLI), `exiftool`, `tesseract`, `yt-dlp`, and `uv`. ImageMagick installs as `convert` on most platforms — there is no standalone `imagemagick` binary.

## Gotchas

- **ImageMagick vs GraphicsMagick** — mediaskills expect **ImageMagick** (`convert` or `magick`). Do not substitute GraphicsMagick.
- **Debian/Ubuntu `convert` conflicts** — some minimal images ship without ImageMagick; the package name is `imagemagick`, binary is `convert`.
- **Tesseract language packs** — default install is English only. For other OCR languages: `brew install tesseract-lang` (macOS) or `apt install tesseract-ocr-<lang>` (Debian).
- **ffmpeg builds vary** — Homebrew and distro packages include most codecs; static builds from third parties may lack libx264. Prefer official package managers for dev/CI.
- **yt-dlp updates frequently** — `brew upgrade yt-dlp` or `pip install -U yt-dlp` if downloads fail due to site changes.
- **uv is optional for bash scripts** — only needed to run Python skills (`uv run scripts/...`).

## Recipes

### Check what's installed

```bash
bash skills/install-media-tools/scripts/doctor.sh
```

Example (partial install):

```json
{"ok": true, "op": "install-media-tools.doctor", "data": {"healthy": false, "installed": ["ffmpeg", "ffprobe"], "missing": ["convert", "exiftool", "tesseract", "yt-dlp", "uv"], "platform": "darwin"}, "output_paths": []}
```

When `healthy` is `false`, run install or install missing packages manually.

### Install via script (macOS or Debian/Ubuntu)

```bash
bash skills/install-media-tools/scripts/install.sh
```

- **macOS** — uses Homebrew: `brew install ffmpeg imagemagick exiftool tesseract yt-dlp uv`
- **Debian/Ubuntu** — uses `apt-get` (may prompt for sudo): `ffmpeg imagemagick libimage-exiftool-perl tesseract-ocr`, then installs `yt-dlp` and `uv` via official install scripts when missing

Re-run `doctor.sh` after install to confirm.

### List detected tools only

```bash
bash skills/install-media-tools/scripts/detect-tools.sh
```

### Resolve a binary path

```bash
bash skills/install-media-tools/scripts/which.sh --tool ffmpeg
# or
bash skills/install-media-tools/scripts/which.sh --args '{"tool": "ffmpeg"}'
```

## Manual install (by platform)

### macOS (Homebrew)

```bash
brew install ffmpeg imagemagick exiftool tesseract yt-dlp uv
```

Optional OCR languages: `brew install tesseract-lang`

### Debian / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg imagemagick libimage-exiftool-perl tesseract-ocr
# yt-dlp (pick one)
sudo apt-get install -y yt-dlp          # if available in your release
# or: sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && sudo chmod a+rx /usr/local/bin/yt-dlp
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Fedora / RHEL

```bash
sudo dnf install -y ffmpeg ImageMagick perl-Image-ExifTool tesseract
pip install yt-dlp   # or use COPR / static binary
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Verify versions

```bash
ffmpeg -version | head -1
convert -version | head -1    # or: magick -version
exiftool -ver
tesseract --version | head -1
yt-dlp --version
uv --version
```

## Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `ffmpeg not found` after install | PATH not updated | Open new shell; run `which.sh --tool ffmpeg` |
| `convert: not authorized` (ImageMagick) | Policy blocks read/write | Edit `/etc/ImageMagick-6/policy.xml` or policy path from `convert -list policy` |
| `tesseract` missing language | Language pack not installed | Install `tesseract-ocr-<lang>` or `tesseract-lang` |
| `yt-dlp` HTTP 403 | Outdated binary | Upgrade yt-dlp |
| `uv: command not found` after curl install | `~/.local/bin` not on PATH | Add `export PATH="$HOME/.local/bin:$PATH"` to shell profile |
| brew install fails on Linux | Homebrew on Linux needs build deps | Prefer native `apt`/`dnf` commands above |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/doctor.sh` | Health check — lists installed vs missing tools |
| `scripts/install.sh` | Attempt automated install (brew or apt + yt-dlp/uv bootstrap) |
| `scripts/detect-tools.sh` | List tools currently on PATH |
| `scripts/which.sh` | Resolve full path for one tool name |

## Do not use for

- Media processing itself (install tools, then use other skills)
- Windows auto-install (manual ffmpeg/uv install on Windows)

## Related skills

- `inspect` — first skill to try after doctor passes ffmpeg/ffprobe
- `download` — requires yt-dlp
- `image`, `speech-captions`, `vision-analysis` — require additional tools from this skill
