# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| Latest release tag | Yes |
| `main` / `master` branch | Best effort |

Install a [tagged release](https://github.com/timelapsetech/mediaskills/releases) for reproducible behavior.

## Reporting a vulnerability

**Do not** open public GitHub issues for security-sensitive reports.

Email **security@timelapsetech.com** (or open a private [GitHub security advisory](https://github.com/timelapsetech/mediaskills/security/advisories/new) if enabled) with:

- Description and impact
- Steps to reproduce
- Affected skill/script and version
- Suggested fix (if any)

We aim to acknowledge within 72 hours.

## Scope

In scope:

- Scripts that execute shell commands (`ffmpeg`, `yt-dlp`, `brew`, `apt`)
- Path traversal or unsafe file writes in script output paths
- Dependency issues in PEP 723 inline dependencies

Out of scope:

- Malicious media files used intentionally with ffmpeg (users should only process trusted assets)
- Third-party binaries (ffmpeg, yt-dlp) — report upstream
- Agent prompt injection via SKILL.md (mitigate in your agent's tool policies)

## Safe usage

- Run `doctor.sh` before processing untrusted environments.
- Set `MEDIASKILLS_DATA_DIR` to an isolated directory when testing unknown inputs.
- Do not pass unsanitized URLs to `download/url.py` without reviewing yt-dlp's behavior.
