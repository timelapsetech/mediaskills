# Changelog

All notable changes to this project are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.2] - 2026-07-15

### Added

- `forced-narrative-exact` skill: dense caption-band OCR discovery, agent-verified seeds, source-frame boundary refinement, Markdown/JSON/CSV/SRT delivery, and texted/textless completeness audit
- `program-master` doctor, self-test, profile-driven `run_report.py` delivery bundle, thumbnail-led PDF reports, and versioned `profiles/broadcast-default.json`
- Workflows for program-master segment reports and exact forced-narrative inventories

### Changed

- `program-master` upgraded to fade-aware separators, provenance/QC manifests, and fail-closed bundle validation
- Agent routing and docs distinguish `forced-narrative-exact` (exact burned-in dialogue) from `vision-analysis` (broader on-screen text/graphics)
- Shared `main_wrapper` now maps subprocess and runtime failures to the JSON error contract

## [0.1.1] - 2026-07-06

### Added

- **program-master** — embedded SMPTE timecode mapping from tmcd tracks (`--timecode-mode embedded`); agent-ready `compile.py` reports (`*_program_master_report.json` with `rows` + `episode` metadata)
- **vision-analysis** — `compile_forced_narrative_report.py` (`vision.compile_forced_narrative_report`) for OCR-path forced-narrative dialogue tables; agent deliverable format docs for forced narrative
- **install-media-tools** — output path reference table (workspace `.mediaskills/generated/` vs `downloads/`)

### Changed

- **All skills** — outputs resolve to **workspace root** `.mediaskills/` (walk up to `.agents/skills`), not `cwd` inside a skill folder; shared `workspace_root()` / `mediaskills_dir()` helpers in `_mediaskills_common.py`
- **`MEDIASKILLS_DATA_DIR`** — now the base for all `.mediaskills/*` subfolders (not only `generated/`)
- **program-master** `compile.py` — writes structured report JSON instead of echoing the raw manifest; Markdown table uses embedded TC and human durations
- **timecode** — docs and `calculate.py` for mapping file seconds to embedded SMPTE with exact rational fps (`30000/1001`)

### Fixed

- Download and generated outputs no longer land inside `.agents/skills/<skill>/` when agents `cd` into a skill directory

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

[0.1.2]: https://github.com/timelapsetech/mediaskills/releases/tag/v0.1.2
[0.1.1]: https://github.com/timelapsetech/mediaskills/releases/tag/v0.1.1
[0.1.0]: https://github.com/timelapsetech/mediaskills/releases/tag/v0.1.0
