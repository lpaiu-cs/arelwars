# AW2 Phase 1 / Phase 2 Oracle Status

Audit date: 2026-04-03

## Result

- `Phase 1 = blocked`
- `Phase 2 = blocked`

## Why

The blocker is upstream from both phases:

- [aw2-phase0-installability-gate.md](/C:/vs/other/arelwars/docs/aw2-phase0-installability-gate.md) already established that the current machine has no Android runtime that can actually execute the original AW2 APK

Therefore:

- Phase 1 cannot launch the original package into a stable observable scene
- Phase 2 cannot probe real oracle backends against a live original process

## What Was Still Completed

The AW2-specific oracle harness now exists:

- [capture_aw2_oracle_trace.py](/C:/vs/other/arelwars/tools/arel_wars2/capture_aw2_oracle_trace.py)

It is a direct AW2 wrapper over the proven AW1 capture harness and preserves the same evidence classes:

- package identity
- JNI backend capability truth
- frame hashes
- audio cues
- save snapshots
- scene transitions
- verification trace scaffold

The AW2 protocol is also fixed:

- [aw2-verification-protocol.md](/C:/vs/other/arelwars/docs/aw2-verification-protocol.md)

## Immediate Consequence

Until an external ARM-capable Android runtime exists, Phases 1 and 2 cannot be approved.

The only productive work that remains inside the current machine is:

- AW2 static bootstrap and asset-truth freezing
- route decision documentation
- packaging-track gate hardening
