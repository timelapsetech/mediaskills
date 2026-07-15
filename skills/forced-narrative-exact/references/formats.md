# Seed, refined, and override formats

## Seed JSON

Use file-relative decimal seconds for approximate windows. Keep them wide enough to contain the cue's first and last visible frames.

```json
{
  "input_path": "/path/to/master.mp4",
  "program_pass": 1,
  "program_passes": {
    "pass_1": "contains burned-in forced narrative",
    "pass_2": "textless duplicate; no forced-narrative rows"
  },
  "crop": {"x": 0, "y": 500, "width": 1280, "height": 220},
  "cues": [
    {
      "id": 1,
      "approx_start": 140.5,
      "approx_end": 143.5,
      "speaker": "Trooper Stephens",
      "lines": ["[Trooper Stephens]", "Dude, $102,000 in warrants?"]
    }
  ]
}
```

IDs must be unique positive integers in chronological order. `lines` is authoritative literal text. Join it with `\n` for `text`.

## Refined JSON

`refine_boundaries.py` adds exact frame, second, SMPTE, and QC fields:

```json
{
  "id": 1,
  "program_pass": 1,
  "start_frame": 4212,
  "end_frame_exclusive": 4316,
  "duration_frames": 104,
  "start_seconds": 140.5404,
  "end_seconds": 144.010533,
  "start_timecode": "00:02:20;16",
  "end_timecode": "00:02:24;00",
  "embedded_start_timecode": "01:01:00;16",
  "embedded_end_timecode": "01:01:04;00",
  "speaker": "Trooper Stephens",
  "lines": ["[Trooper Stephens]", "Dude, $102,000 in warrants?"],
  "text": "[Trooper Stephens]\nDude, $102,000 in warrants?",
  "qc": {"reference_frame": 4256, "matched_word_boxes": 6, "peak_score": 1.0, "threshold": 0.72, "needs_review": false}
}
```

`build_report.py` preserves each row's `qc` object in the authoritative report JSON so validators and reviewers can distinguish unresolved warnings from visually completed manual overrides.

## Override JSON

Use overrides only after inspecting boundary frames. An override may provide only corrected boundaries or replace the full cue. Frame fields are authoritative; the report builder recomputes timing fields.

```json
{
  "input_path": "/path/to/master.mp4",
  "rows": [
    {
      "id": 17,
      "start_frame": 8104,
      "end_frame_exclusive": 8152,
      "review_note": "Visually checked previous/start/last/end frames."
    }
  ]
}
```

Never use an override to conceal a missing cue or uncertain transcription.

## Completeness review JSON

After the first `audit_completeness.py` pass, create a review document keyed to the exact uncovered intervals:

```json
{
  "candidates": [
    {
      "start_frame": 15949,
      "end_frame_exclusive": 15978,
      "disposition": "missing_dialogue",
      "review_note": "Visible subtitle: I’m a clergywoman. Add it to the seed and rerun."
    },
    {
      "start_frame": 17884,
      "end_frame_exclusive": 17930,
      "disposition": "excluded_non_dialogue_text",
      "review_note": "CAM / SECURITY / SAFETY lower third; not dialogue."
    }
  ]
}
```

Allowed dispositions are:

- `missing_dialogue`: a real burned-in dialogue state absent from the report; blocks delivery.
- `subtitle_boundary_residual`: subtitle pixels immediately outside a reported cue; blocks delivery.
- `excluded_non_dialogue_text`: a visually confirmed title, lower third, time/location bug, credit, or other excluded graphic.
- `alignment_artifact`: a visually confirmed picture mismatch or transition difference with no subtitle text.

Every candidate requires a nonempty `review_note`. After correcting blocking findings, rerun the audit against the corrected report and create a fresh review whose intervals exactly match the new audit.
