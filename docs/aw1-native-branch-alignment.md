# AW1 Native Branch Alignment

This note records the corrections imported from the native-disassembly side so the `main` branch does not overstate heuristic findings.

Audit sync date: 2026-04-02

## What Changed

- `PZX` root offsets are now treated as a typed subresource graph.
  - `field4 -> PZD`
  - `field8 -> PZF`
  - `field12 -> PZA`
- Embedded `PZA` is now documented as the authoritative base-clip timing carrier when present.
- Embedded `PZF` is now documented as the frame-composition owner.
- Tail sections are still useful, but they are described as `tail-group candidates` or `post-frame grouped sections`, not as a closed native timing format.
- `MPL` bank switching stays anchored to item flags:
  - `flag == 0 -> bank B`
  - `flag > 0 -> bank A`
- `179` stays isolated as a special packed-pixel case and is no longer described as a general palette rule.

## Certainty Levels

The main branch should prefer these labels:

- `native-confirmed`
- `asset-structural`
- `runtime-consistent heuristic`
- `donor/prototype inferred`

Applied interpretation:

- `PZX -> PZD/PZF/PZA` root typing: `native-confirmed`
- `PZA clip/delay table` parsing: `native-confirmed`
- `PZF frame-pool header` parsing: `asset-structural`
- `timelineKind`, `tail-group candidate`, overlay cadence, and grouped tail playback: `runtime-consistent heuristic`
- donor-filled playback cadence: `donor/prototype inferred`

## Main-Branch Corrections

1. Exported preview/runtime metadata now carries explicit certainty labels instead of treating all recovered timing fields equally.
2. `preview_manifest.json` now exports typed `PZD/PZF/PZA` root summaries per stem.
3. UI text was corrected to describe `timelineKind` as a heuristic class and tail sections as heuristic overlay groupings.
4. Render semantics now distinguish:
   - `MPL` flag-driven switching as the strong/native-aligned rule
   - `179` as an asset-structural special case
   - `PTC` emitter semantics as runtime-consistent reconstruction

## Remaining Caution

- The runtime still uses grouped overlay cadence for preview playback because those grouped events are what the current scene renderer consumes.
- When a stem exposes embedded `PZA`, its `delay` should be treated as the native base-clip timing source.
- That does not automatically make heuristic overlay cadence native. The two layers should stay separate until a matching native consumer is identified for the grouped tail markers.
