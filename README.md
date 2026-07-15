# mediaskills

Open-source [Agent Skills](https://agentskills.io) for media processing — portable instructions and scripts that help AI agents work with video, audio, images, captions, and broadcast formats.

[![Skills](https://img.shields.io/badge/skills-14-blue)](skills/index.json)
[![Tests](https://img.shields.io/badge/tests-102%2B-green)](./scripts/smoke.sh)
[![Spec](https://img.shields.io/badge/agentskills.io-compliant-purple)](https://agentskills.io/specification)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Repository:** [timelapsetech/mediaskills](https://github.com/timelapsetech/mediaskills)  
**Home (site):** [mediaskills.ai](https://mediaskills.ai)

## Quick start (agents)

Read [AGENTS.md](AGENTS.md) for skill routing. Machine-readable catalog: [skills/index.json](skills/index.json).

```bash
npx skills add timelapsetech/mediaskills@v0.1.2 --skill install-media-tools
npx skills add timelapsetech/mediaskills@v0.1.2 --skill inspect
bash skills/install-media-tools/scripts/doctor.sh
```

## Install

```bash
# List available skills
npx skills add timelapsetech/mediaskills@v0.1.2 --list

# Install all skills (pin @v0.1.2 for reproducibility)
npx skills add timelapsetech/mediaskills@v0.1.2 --all

# Install one skill
npx skills add timelapsetech/mediaskills@v0.1.2 --skill inspect

# Install globally
npx skills add timelapsetech/mediaskills@v0.1.2 -g --skill audio
```

## System dependencies

```bash
bash skills/install-media-tools/scripts/doctor.sh
bash skills/install-media-tools/scripts/install.sh   # macOS (brew) or Debian/Ubuntu (apt)
```

Python scripts use [uv](https://docs.astral.sh/uv/) (`uv run scripts/foo.py`) with PEP 723 inline dependencies.

| Skill | Extra requirements |
| --- | --- |
| `speech-captions` | faster-whisper (via `uv run`); models download on first use |
| `image`, `vision-analysis`, `forced-narrative-exact` | tesseract; ImageMagick `convert` (image/vision-analysis) |
| `download` | yt-dlp |
| `timecode` | PyPI `timecode` (auto via `uv run`) |

**Tested:** macOS, Ubuntu/Debian, Python 3.11–3.13, ffmpeg 6.x/7.x. See [CHANGELOG.md](CHANGELOG.md).

## Skills (14)

| Skill | Description |
| --- | --- |
| `install-media-tools` | Detect and install ffmpeg, ImageMagick, exiftool, tesseract, yt-dlp, uv |
| `inspect` | Probe, describe, compare, and batch-inspect media files |
| `audio` | Convert, trim, concat, normalize, fade, resample, silence-detect |
| `image` | Convert, resize, crop, rotate, flip, optimize, EXIF, OCR |
| `video-transformation` | Trim, concat, transcode, scale, proxy, extract, GIF, mux |
| `download` | Download media from URLs via yt-dlp |
| `timecode` | SMPTE timecode math (DF/NDF), conversion, and extraction |
| `speech-captions` | Whisper transcription, SRT/VTT export, language detection |
| `subtitles` | Convert, shift, extract, burn subtitles |
| `captions-compliance` | Caption rules, validation, SCC/SMPTE-TT export, busy zones |
| `shots` | Shot/cut detection and midpoint frame extraction |
| `program-master` | Fade-aware black+silence segmentation, labeled manifests, thumbnail PDF reports |
| `forced-narrative-exact` | Exhaustive frame-accurate burned-in dialogue inventory and completeness QC |
| `vision-analysis` | Frame extraction, agent-guided analysis, on-screen text reports |

Each `SKILL.md` includes when-to-use, gotchas, recipes, and **do not use for** boundaries.

## Documentation

| Doc | Audience |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Agent skill routing |
| [docs/SCRIPT_CONTRACT.md](docs/SCRIPT_CONTRACT.md) | JSON stdout contract |
| [docs/ERRORS.md](docs/ERRORS.md) | Common failures |
| [docs/workflows/](docs/workflows/) | End-to-end cookbooks |
| [docs/COMPARISON.md](docs/COMPARISON.md) | vs raw ffmpeg / MCP |
| [docs/FIXTURES.md](docs/FIXTURES.md) | Golden test media |
| [SUPPORT.md](SUPPORT.md) | Supported platforms |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

## Script contract

```json
{"ok": true, "op": "inspect.probe", "data": {...}, "output_paths": ["/path/to/output"]}
```

Exit codes: `0` ok · `1` bad args · `2` missing binary · `3` processing failure.

Full spec: [docs/SCRIPT_CONTRACT.md](docs/SCRIPT_CONTRACT.md).

## Development

```bash
./scripts/bootstrap.sh
./scripts/smoke.sh --full          # pre-publish gate
./scripts/install-git-hooks.sh   # optional: smoke on git push
```

| Command | Purpose |
| --- | --- |
| `./scripts/check.sh` | Fast: validate, index check, pytest |
| `./scripts/smoke.sh` | Doctor + check.sh |
| `./scripts/smoke.sh --full --whisper` | Full confidence before release |
| `python scripts/list_ops.py --write` | Refresh `skills/index.json` |

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE). [Code of Conduct](CODE_OF_CONDUCT.md).
