# Common errors and fixes

Quick routing for agents and humans when scripts fail.

## Missing binaries (exit code 2)

| Message | Fix |
| --- | --- |
| `ffmpeg not found` | `bash skills/install-media-tools/scripts/install.sh` or `brew install ffmpeg` |
| `ffprobe not found` | Same as ffmpeg (usually bundled) |
| `tesseract not found` | `brew install tesseract` — needed for `image/ocr.py`, `vision-analysis/compile_report.py` |
| `convert not found` | ImageMagick: `brew install imagemagick` |
| `yt-dlp not found` | `brew install yt-dlp` for `download/url.py` |

Run `bash skills/install-media-tools/scripts/doctor.sh` for a full report.

## Media probe / input (exit code 3)

| Symptom | Likely cause | Skill / action |
| --- | --- | --- |
| `moov atom not found` | Incomplete MP4 download | Re-download (`download`) or remux |
| `Invalid data found` | Corrupt or wrong file | `inspect` probe; verify extension |
| `No video stream` | Audio-only file | Use `audio` skill, not video scripts |
| `No embedded subtitle track` | No `s:` stream | `speech-captions` or external SRT |
| Duration mismatch audio/video | Bad mux | `inspect` compare; trim shorter stream |

## Timecode

| Symptom | Cause | Fix |
| --- | --- | --- |
| Off by ~3.6 s/hour | Drop-frame vs non-drop-frame | `timecode/detect_format.py`; check `;` vs `:` |
| Segment TC drifts on broadcast master | Rounded 30 fps instead of `30000/1001` | Use exact rational from ffprobe; `program-master --timecode-mode embedded` |
| Wrong cross-fps result | Used frame index vs wall-clock | `convert.py` defaults to `--preserve realtime` |
| `timecode: null` in extract | No tag in container | Derive from fps + duration; proxies lack tmcd — use source master |

## Output paths

| Symptom | Cause | Fix |
| --- | --- | --- |
| Files under `.agents/skills/...` | Pre-0.1.1 cwd-relative paths | Upgrade to 0.1.1+; outputs belong at workspace `.mediaskills/` |
| Cannot find generated manifest | Looking in skill folder | Check `<workspace>/.mediaskills/generated/` or set `MEDIASKILLS_DATA_DIR` |

## Video transformation

| Symptom | Cause | Fix |
| --- | --- | --- |
| Frozen first frame after trim | Cut on non-keyframe with stream copy | Re-run trim with re-encode fallback or shorter GOP source |
| Concat failed then worked | Codec/resolution mismatch | Fallback re-encode ran — expected |
| Replace audio too short | `-shortest` ended on audio | Extend audio or pad |

## Captions

| Symptom | Cause | Fix |
| --- | --- | --- |
| Overlap / long line flags | Source SRT issues | `captions-compliance/format.py` |
| SCC validation errors | Unsupported characters | `validate.py` output lists issues |
| Empty transcription | Silence or model too small | Larger Whisper model; check audio track |

## Agent mistakes (not script bugs)

| Mistake | Correct skill |
| --- | --- |
| Used `transcode.py` to mux external audio | `video-transformation/replace_audio.py` |
| Burned captions when soft subs needed | `subtitles` extract/mux, not `burn.py` |
| Normalized audio but didn't mux back | `video-transformation/replace_audio.py` |
| Used raw ffmpeg when JSON chain needed | Use skill scripts for `output_paths` |

## Getting more help

1. Re-run with `--help`
2. `./scripts/smoke.sh --full`
3. [GitHub issues](https://github.com/timelapsetech/mediaskills/issues) with JSON output
