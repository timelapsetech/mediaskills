# Operation ID namespaces

Stable `op` values returned in JSON stdout. Generated from scripts — see `python scripts/list_ops.py`.

| Prefix | Skill directory |
| --- | --- |
| `inspect.*` | `skills/inspect/` |
| `audio.*` | `skills/audio/` |
| `video.*` | `skills/video-transformation/` |
| `image.*` | `skills/image/` |
| `timecode.*` | `skills/timecode/` |
| `speech_captions.*` | `skills/speech-captions/` |
| `caption.*` | `skills/captions-compliance/` |
| `subtitles.*` | `skills/subtitles/` |
| `download.*` | `skills/download/` |
| `shots.*` | `skills/shots/` |
| `program_master.*` | `skills/program-master/` |
| `forced_narrative_exact.*` | `skills/forced-narrative-exact/` |
| `vision.*` | `skills/vision-analysis/` |
| `install-media-tools.*` | `skills/install-media-tools/` (bash) |

## Naming convention

- Python skills: `{namespace}.{snake_case_action}` matching the script purpose
- Underscores in skill folder names (`speech-captions`) map to `speech_captions` in ops
- Hyphens in script filenames (`to-srt.py`) map to underscores in ops (`to_srt`)

## Discovering ops programmatically

```bash
python scripts/list_ops.py
python scripts/list_ops.py --write   # refresh skills/index.json
python scripts/list_ops.py --check # CI/smoke: fail if index stale
```
