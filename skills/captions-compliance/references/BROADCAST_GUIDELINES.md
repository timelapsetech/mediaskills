# Broadcast caption guidelines (reference)

High-level context for `captions-compliance` scripts. **Not legal advice.** Verify with your distributor (station, Netflix, PBS, etc.).

## FCC-oriented heuristics (U.S.)

| Concern | Typical target | mediaskills script |
| --- | --- | --- |
| Characters per line | ≤ 32 (608) / ≤ 42 comfort | `validate.py`, `format.py` |
| Lines on screen | ≤ 2 | `validate.py` |
| Duration on screen | ~1–7 seconds | `validate.py`, `rules.py` |
| Reading speed | ~15–20 characters/sec | `rules.py` |
| Safe area / busy zones | Avoid graphics overlap | `apply-busy-zones.py` |

## Export formats

| Format | Script | Notes |
| --- | --- | --- |
| CEA-608 SCC | `to-scc.py` | Scenarist-style; line-21 oriented |
| SMPTE-TT / TTML | `to-smpte-tt.py` | XML timed text |
| SRT cleanup | `format.py` | Wrap long lines, basic fixes |

## Workflow

1. Obtain SRT (`speech-captions` or manual)
2. `validate.py` → fix issues
3. `format.py` → normalized SRT
4. Export SCC/SMPTE-TT as required

## Out of scope

- Closed-caption legal certification
- Full EBU-TT / IMSC1 feature sets
- Live captioning latency requirements

See [docs/workflows/broadcast-captions.md](../../docs/workflows/broadcast-captions.md).
