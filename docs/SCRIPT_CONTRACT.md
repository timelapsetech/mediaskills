# Script contract

All mediaskills Python CLI scripts follow this contract unless noted in the skill's `SKILL.md`.

## Success response

One JSON object on **stdout** (last line is canonical if progress lines precede it):

```json
{
  "ok": true,
  "op": "inspect.probe",
  "data": { },
  "output_paths": ["/absolute/or/relative/path"]
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `ok` | boolean | Always `true` on success |
| `op` | string | Stable operation ID (`skill.action`) |
| `data` | object | Operation-specific payload |
| `output_paths` | string[] | Files created or primary outputs |

## Error response

JSON on **stderr**, non-zero exit:

```json
{
  "ok": false,
  "op": "inspect.probe",
  "error": "Human-readable message"
}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Bad arguments / usage |
| `2` | Missing dependency (binary not on PATH) |
| `3` | Processing failure (ffmpeg error, invalid media, etc.) |

## Progress

Optional progress objects on **stderr** during long operations:

```json
{"progress": 45.0, "stage": "transcoding"}
```

Agents should parse **stdout** for the final result; treat stderr as logs unless parsing progress.

## Environment

| Variable | Purpose |
| --- | --- |
| `MEDIASKILLS_DATA_DIR` | Base directory for all `.mediaskills/*` outputs (`generated/`, `downloads/`, etc.). Absolute path recommended in CI. |

Default output: `<workspace>/.mediaskills/generated/` at the repo root — the directory that contains `.agents/skills`. Scripts walk up from the skill script path to find it; if not found, they fall back to `cwd`. Outputs never land inside `.agents/skills/<skill>/`.

## Invocation

From a skill directory:

```bash
uv run scripts/probe.py --input /path/to/file.mp4
```

PEP 723 inline dependencies are resolved automatically by `uv run` — no separate `pip install`.

## Parsing guidance for agents

1. Run the script; capture stdout and exit code.
2. Parse the **last non-empty line** of stdout as JSON.
3. If `ok` is true, use `data` and `output_paths` for the next step **only after semantic checks below**.
4. If exit code is `2`, run `install-media-tools` doctor/install.
5. If exit code is `3`, read `error` and consult [ERRORS.md](ERRORS.md).

## Semantic checks (beyond `ok: true`)

`ok: true` means the script finished under the contract — not that the media or report matches the user's intent. Agents must also:

1. Confirm every `output_paths` entry exists and has non-zero size.
2. For transforms, re-probe with `inspect` (`describe.py` / `compare.py`) — duration, codec, resolution, stream counts vs request.
3. Run domain validators when the skill provides them:
   - `program_master.validate_report` / QC `passed: true`
   - `forced_narrative_exact.validate_report` / completeness `publication_ready: true`
   - `vision.validate_analysis` before on-screen text reports
   - `caption.validate` before SCC / SMPTE-TT export
4. Follow the skill's **Acceptance checks** in `SKILL.md` and [AGENTS.md](../AGENTS.md) **Always verify before deliver**.

Optional CLI helper: `python scripts/verify_output.py` (path existence, optional duration bounds).

## Bash scripts (install-media-tools)

Same JSON contract on stdout. Example:

```bash
bash skills/install-media-tools/scripts/doctor.sh
```

## Versioning

Operation IDs (`op`) are stable within a semver minor release. New scripts may be added; existing `op` values should not change meaning without a major version bump.

See [CHANGELOG.md](../CHANGELOG.md).
