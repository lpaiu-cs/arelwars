# AW2 Phase 4 Route Decision

Audit date: 2026-04-03

## Decision

- `Route A` is now selected
- label: `live-original oracle enabled -> original-equivalence / packaging track`

## Why Route A Now Applies

The earlier blocker was “the original AW2 APK cannot run as a live oracle on this machine.”

That is no longer true.

The current environment now provides:

- a live `BlueStacks Nougat32` guest
- `adb` visibility as `emulator-5554`
- original APK install success
- original process launch success
- oracle probe and capture artifacts with package identity, screenshots, UI, scene focus, and profiler output

Primary evidence:

- [aw2-phase0-installability-gate.md](/C:/vs/other/arelwars/docs/aw2-phase0-installability-gate.md)
- [aw2-phase1-phase2-oracle-status.md](/C:/vs/other/arelwars/docs/aw2-phase1-phase2-oracle-status.md)
- [probe-live-rerun.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/probe-live-rerun.json)
- [live-drm-smoke-v4/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/session.json)

## Why Route B Is No Longer The Best Fit

`Route B` was the fallback for “the original package runs, but oracle evidence is too weak.”

That is now too pessimistic.

The environment already captures:

- package identity
- focused component / scene focus
- frame hashes
- UI dumps
- profiler artifacts
- logcat

This is enough to proceed with oracle-driven equivalence work.

## Why Route C Is No Longer Correct

`Route C` assumed the original package could not install or boot.

That is now false.

The original package is both:

- installable
- observable

So Route C must be retired.

## Consequence

From this point:

- AW2 packaging work is no longer environment-blocked
- the next approved step is x64/runtime bootstrap against the live oracle
- static reverse-engineering stays useful, but it is no longer the only productive track

## Next Approved Work

The track may now advance to:

- `Phase 5` AW2 x64 runtime bootstrap
- `Phase 6` runtime trace schema alignment
- representative equivalence work after that
