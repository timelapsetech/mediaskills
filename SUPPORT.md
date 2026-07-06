# Support

## What we support

- **13 Agent Skills** for local media processing via ffmpeg and related tools
- **Python 3.11+** scripts run with `uv run`
- **macOS and Linux** (Ubuntu/Debian) for `install-media-tools`
- Spec compliance with [agentskills.io](https://agentskills.io)

## What is best-effort

- Windows (scripts may work if ffmpeg/uv are on PATH; `install.sh` is not tailored for Windows)
- Proprietary codecs/containers without ffmpeg support (MXF, some broadcast wrappers)
- Legal certification of caption compliance (heuristics only — verify with your distributor)
- Real-time or live stream processing

## Getting help

1. Run `bash skills/install-media-tools/scripts/doctor.sh` and fix missing binaries.
2. Run `./scripts/smoke.sh --full` and include failures in your report.
3. Open a [GitHub issue](https://github.com/timelapsetech/mediaskills/issues) with:
   - Skill name and script
   - Full command
   - JSON stdout/stderr (redact paths if needed)
   - OS and `ffmpeg -version` first line

## Version pinning

```bash
npx skills add timelapsetech/mediaskills@v0.1.1 --skill inspect
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.
