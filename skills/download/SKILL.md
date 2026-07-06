---
name: download
description: Download video and audio from URLs using yt-dlp. Use when you need to fetch media from YouTube, Vimeo, or other supported sites before local processing with inspect, audio, or video-transformation skills.
license: MIT
compatibility: Requires yt-dlp on PATH. Scripts are Python 3.11+, run via `uv run`. Network access required.
metadata:
  mediaskills-category: acquire
  mediaskills-binaries: yt-dlp
---

# Download

Fetch remote media with yt-dlp. Use this skill when you have a **URL** and need a **local file** for downstream processing.

## When to use

- **This skill** — download from YouTube, Vimeo, Twitter/X, and hundreds of other sites supported by yt-dlp.
- **`inspect`** — after download, probe the file for duration, codecs, and resolution.
- **`audio` / `video-transformation`** — trim, transcode, or extract audio from downloaded files.

## Gotchas

- **Network required** — downloads fail offline or behind restrictive firewalls. Corporate proxies may need `HTTP_PROXY` / `HTTPS_PROXY` env vars.
- **Rate limits and bot checks** — some sites block datacenter IPs or require cookies. Pass cookies via yt-dlp config (`~/.config/yt-dlp/config`) if downloads fail with 403/429.
- **Output location** — files land in `.mediaskills/downloads/` (cwd) or `$MEDIASKILLS_DATA_DIR/downloads/` when set. Filename pattern: `Title [video_id].ext`.
- **Playlists** — this script downloads the URL as given; playlist URLs may fetch multiple files. Prefer single-video URLs for predictable output.
- **Live streams** — live content may produce partial files if recording is interrupted.
- **Legal / ToS** — only download content you have rights to access. Respect platform terms and copyright.

## Recipes

### Download a video

```bash
uv run scripts/url.py --url 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
```

Example result:

```json
{"ok": true, "op": "download.url", "data": {"url": "...", "output_path": "/path/.mediaskills/downloads/Title [id].mp4", "output_dir": "/path/.mediaskills/downloads"}, "output_paths": ["..."]}
```

### Custom data directory (CI or server)

```bash
export MEDIASKILLS_DATA_DIR=/var/mediaskills
uv run scripts/url.py --url 'https://example.com/clip.mp4'
```

Downloads go to `/var/mediaskills/downloads/`.

### Chain with inspect

```bash
uv run scripts/url.py --url 'https://...' | jq -r '.output_paths[0]' | xargs -I{} uv run ../inspect/scripts/probe.py --input {}
```

## Troubleshooting

| Error / symptom | Likely cause | Action |
| --- | --- | --- |
| `yt-dlp not found` | Binary missing | `brew install yt-dlp` or `pip install yt-dlp` |
| `HTTP Error 403` | Geo-block or auth required | Update yt-dlp (`yt-dlp -U`); try browser cookies |
| `Video unavailable` | Removed or private | Verify URL in a browser while logged in |
| Output file not found | Print hook failed | Check `output_dir` for newest file; retry with verbose yt-dlp |
| Slow download | Large file or throttling | Normal; progress JSON emitted on stderr |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/url.py` | Download media from a URL |

## Do not use for

- Local file processing without a URL
- DRM-protected streams you cannot access with yt-dlp

## Related skills

- `inspect` — probe downloaded files
- `install-media-tools` — install ffmpeg/ffprobe for post-download work
- `audio`, `video-transformation` — process downloaded media
