# Agent routing guide

Start here when choosing a mediaskills skill. Install with:

```bash
npx skills add timelapsetech/mediaskills@v0.1.2 --skill <name>
```

Machine-readable catalog: [`skills/index.json`](skills/index.json). Regenerate with `python scripts/list_ops.py --write`.

## Decision tree

```
Need metadata only (no file changes)?
  └─ inspect

Need to change video (cut, transcode, resize, mux, GIF, frame grab)?
  └─ video-transformation

Need audio-only edits?
  └─ audio  (mux back to video → video-transformation replace_audio.py)

Need SMPTE timecode math (DF/NDF, fps conversion)?
  └─ timecode

Need captions from speech?
  └─ speech-captions → captions-compliance / subtitles

Need subtitle file ops (SRT/VTT shift, burn-in)?
  └─ subtitles

Need broadcast caption compliance (SCC, SMPTE-TT, validation)?
  └─ captions-compliance

Need shot boundaries or midpoint frames?
  └─ shots

Need program segmentation (blacks, silence, acts)?
  └─ program-master

Need exhaustive frame-accurate burned-in dialogue / forced narrative?
  └─ forced-narrative-exact

Need on-screen text / vision analysis workflow?
  └─ vision-analysis  (agent analyzes frames; scripts merge JSON)

Need to download from URL?
  └─ download

Missing ffmpeg / tools?
  └─ install-media-tools  (doctor.sh first)
```

## Always do first

1. `bash skills/install-media-tools/scripts/doctor.sh` — confirm binaries
2. `inspect` probe/describe — confirm duration, codecs, streams before destructive ops
3. Read the target skill's **Do not use for** section in `SKILL.md`

## Chaining outputs

Scripts return JSON on stdout. Pass paths from `data.output_path` or `output_paths[]` to the next step.

| From | Field | To |
| --- | --- | --- |
| any transform | `output_paths[0]` | next `--input` |
| timecode | `data.seconds_realtime` | `video-transformation` `--start` / `--end` |
| speech-captions | SRT path | `captions-compliance` validate/format |
| vision-analysis | `manifest_path` | agent frame analysis → `merge_analysis.py` |
| program-master | labeled manifest / report bundle | `forced-narrative-exact` pass scoping |
| forced-narrative-exact | refined JSON / report paths | validate → deliver md/json/csv/srt |

## Op ID namespaces

| Prefix | Skill |
| --- | --- |
| `inspect.*` | inspect |
| `audio.*` | audio |
| `video.*` | video-transformation |
| `image.*` | image |
| `timecode.*` | timecode |
| `speech_captions.*` | speech-captions |
| `caption.*` | captions-compliance |
| `subtitles.*` | subtitles |
| `download.*` | download |
| `shots.*` | shots |
| `program_master.*` | program-master |
| `forced_narrative_exact.*` | forced-narrative-exact |
| `vision.*` | vision-analysis |
| `install-media-tools.*` | install-media-tools (bash) |

Full list: `python scripts/list_ops.py` or [`docs/OP_NAMESPACES.md`](docs/OP_NAMESPACES.md).

## Workflows

End-to-end recipes: [`docs/workflows/`](docs/workflows/).

## Contract

JSON shape, exit codes, env vars: [`docs/SCRIPT_CONTRACT.md`](docs/SCRIPT_CONTRACT.md).

Common errors: [`docs/ERRORS.md`](docs/ERRORS.md).
