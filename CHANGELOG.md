# Changelog

All notable changes to this project are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-07-05

### Added

- Initial public release: 13 Agent Skills for media processing
- Skills: `install-media-tools`, `inspect`, `audio`, `image`, `video-transformation`, `download`, `timecode`, `speech-captions`, `subtitles`, `captions-compliance`, `shots`, `program-master`, `vision-analysis`
- Consistent JSON script contract across Python CLIs
- Local validation: `scripts/check.sh`, `scripts/smoke.sh`, `scripts/smoke_help.py`
- Machine-readable catalog: `skills/index.json`, `scripts/list_ops.py`
- Agent routing: `AGENTS.md`, `docs/workflows/`, `docs/SCRIPT_CONTRACT.md`
- Golden fixtures in `tests/fixtures/`
- 102 pytest integration tests (whisper/network/install opt-in)

### Notes

- `video-transformation` renamed from `video-editing`
- `timecode` skill replaces earlier `smpte` (drop-frame support via eoyilmaz/timecode)

[0.1.0]: https://github.com/timelapsetech/mediaskills/releases/tag/v0.1.0
