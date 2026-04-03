# AW2 Launcher Boundary Alignment

Audit date: 2026-04-04

## Result

The current live-original oracle and the bootstrap runtime now meet at the same launcher boundary.

Comparison artifact:

- [aw2-launcher-boundary-comparison.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-launcher-boundary-comparison.json)

## What Matches

- original oracle reaches `com.gamevil.ArelWars2.global/.ArelWars2Launcher`
- bootstrap runtime reaches `ArelWars2Launcher`
- bootstrap trace now emits a deterministic stage seed:
  - `familyId = 0`
  - `aiIndex = 0`
  - `routeLabel = primary`
  - `preferredMapIndex = 226`
  - `resumeTargetStageBinding = 000`

## External Gate

The original launcher immediately exposes the external dependency boundary:

- title: `Network Error`
- buttons: `Retry`, `End`

That gate is acknowledged in the comparison report rather than treated as an unresolved decode failure.

## Practical Meaning

This gives the AW2 work a valid offline handoff point:

- live original runtime proves the launcher boundary
- bootstrap runtime proves seeded stage-bootstrap metadata at that boundary
- future work can keep pushing `stage 000` bootstrap alignment without blocking on dead remote services
