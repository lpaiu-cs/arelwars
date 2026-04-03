# AW2 Stage Bootstrap Candidates

Audit date: 2026-04-03

This note records the first structural candidate mapping for AW2 stage-bootstrap fields.

Primary artifact:

- [aw2_bootstrap_stage_candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/aw2_bootstrap_stage_candidates.json)

Generator:

- [export_bootstrap_stage_candidates.py](/C:/vs/other/arelwars/tools/arel_wars2/export_bootstrap_stage_candidates.py)

## What This Uses

The candidate report combines three static sources:

- decoded `eng/script/*.zt1.events.json`
- decoded `table/XlsAi.zt1.bin`
- decoded `table/XlsMap.zt1.bin`

The strongest repeating pattern currently visible is:

- script stems appear in paired form:
  - `000`, `001`
  - `010`, `011`
  - `020`, `021`
  - ...
- `XlsAi` rows also alternate in even/odd pairs
- `XlsMap` contains exactly `16` rows, which cleanly fit `8` family pairs

## Current Candidate Rule

For early paired stage scripts, the strongest structural candidate is:

- `familyIdCandidate = stageStem // 10`
- `routeSlotCandidate = stageStem % 10`
- `aiIndexCandidate = familyIdCandidate * 2 + routeSlotCandidate`
- `preferredMapIndexCandidate = XlsMap[row=aiIndexCandidate].u16[1]`

Examples:

- `000 -> family 0, route 0, aiIndex 0, preferredMapIndex 226`
- `001 -> family 0, route 1, aiIndex 1, preferredMapIndex 482`
- `010 -> family 1, route 0, aiIndex 2, preferredMapIndex 216`
- `011 -> family 1, route 1, aiIndex 3, preferredMapIndex 472`

## Important Limit

These are still candidates, not certified runtime truth.

They are useful because:

- they align script-pair numbering with `XlsAi` even/odd row pairing
- they align the same pair index with `XlsMap`
- the first `eng/script/000` dialogue content matches the first `XlsAi` stage title family around `Destroin`

They are not yet sufficient to populate `verificationTrace.familyId`, `aiIndex`, or `preferredMapIndex` as final truth inside the runtime.

## Immediate Use

Use this report as the next narrowing layer for:

- Phase 6 semantic stage-bootstrap trace fields
- original oracle replay capture beyond DRM
- later differential checks once launcher/title flow is opened

