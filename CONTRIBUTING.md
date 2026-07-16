# Contributing to mediaskills

Thank you for helping improve Agent Skills for media processing.

## Local quality gate (no cloud test CI)

GitHub Actions only deploys the documentation site. Skill correctness is enforced on your machine via `smoke.sh` and the pre-push hook.

```bash
./scripts/bootstrap.sh   # first time: uv sync + installs pre-push hook
./scripts/smoke.sh       # before every push / PR
```

For full local confidence before a release:

```bash
./scripts/smoke.sh --full --self-test --whisper
```

`./scripts/smoke.sh` runs:

1. `doctor.sh` — verifies core binaries (`ffmpeg`, `ffprobe`, `uv`); warns on optional tools
2. `./scripts/check.sh` — sync, agentskills validate, pytest

Optional flags:

| Flag | Adds |
| --- | --- |
| `--full` | `--help` smoke on every CLI script (`scripts/smoke_help.py`) |
| `--self-test` | program-master / forced-narrative-exact golden self-tests |
| `--whisper` | `MEDIASKILLS_RUN_WHISPER=1` speech-captions integration tests |
| `--install` | Runs `install-media-tools` `install.sh` (may invoke brew/apt) |

Fast inner loop while editing:

```bash
./scripts/check.sh
```

`./scripts/install-git-hooks.sh` (also run by bootstrap) installs a pre-push hook that runs `./scripts/smoke.sh`.

## Adding or updating a skill

1. Create `skills/<name>/SKILL.md` with valid [agentskills.io](https://agentskills.io/specification) frontmatter (`name` must match directory).
2. Write **useful** instructions — not just a script table. Include when-to-use, gotchas, recipes, parameter tuning, and troubleshooting.
3. Add scripts under `skills/<name>/scripts/`:
   - Python 3.11+ with PEP 723 inline dependencies
   - Real argparse flags (`--input`, `--output`, etc.) — no `--args JSON` blobs
   - `--help` with examples
   - JSON result on stdout; diagnostics on stderr
   - Exit codes: 0 ok, 1 bad args, 2 missing binary, 3 processing failure
4. Import shared helpers from `_mediaskills_common.py` (vendored copy).
5. Add `skills/<name>/tests/test_*.py` with subprocess tests.
6. Run `python scripts/sync_shared_libs.py` after editing `_shared/`.
7. Run `uv run agentskills validate skills/<name>` (or `skills-ref validate` if installed globally).
8. Run `python scripts/list_ops.py --write` after adding scripts (updates `skills/index.json`).
9. Run `./scripts/smoke.sh --full --self-test` before opening a PR.

## Optional integration tests

Some tests are skipped unless you opt in:

| Environment variable | Tests |
| --- | --- |
| `MEDIASKILLS_RUN_WHISPER=1` | `speech-captions` transcribe/detect-language; `captions-compliance` pipeline |
| `MEDIASKILLS_RUN_INSTALL=1` | `install-media-tools` `install.sh` smoke |
| `MEDIASKILLS_RUN_NETWORK=1` | `download` live URL test |

Or use `./scripts/smoke.sh --whisper` / `--install` instead of setting variables manually.

## What not to port

- App-specific job queues, asset libraries, or database lineage
- References to proprietary internal tools
- Skills that only make sense inside a specific product UI

## License

By contributing, you agree your contributions are licensed under the MIT License.
