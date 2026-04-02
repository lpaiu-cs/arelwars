# AW2 Phase 4 Route Decision

Audit date: 2026-04-03

## Decision

- `Route C` remains selected
- label: `static reverse-engineering + local runtime reopening`

## Why Route A Is Still Rejected

`Route A` requires the original AW2 APK to run inside the current environment as a live oracle.

That is still not true.

The machine now has a serious candidate runtime:

- `Oracle VBox`
- plus a patched `BlueStacks Nougat32` guest

But that candidate is still below the Route A threshold:

- no `adb-online` guest
- no successful install of the original APK
- no live original scene capture

So `Route A` is not approved yet.

## Why Route B Is Still Rejected

`Route B` would mean the original package runs but evidence quality is weak.

That also is not the current state.

The blocker is still earlier:

- the local candidate runtime has not crossed into a usable original process

So Route B would still understate the problem.

## Why Route C Is Still Correct

`Route C` still best matches the observed state:

- packaging work is blocked
- original-equivalence work is blocked
- static reverse-engineering remains productive
- local runtime reopening work is now also productive and should continue

## Consequence

From this point:

- do not start `Phase 5` through `Phase 10` as approved packaging work
- do not claim AW2 x64 packaging is in progress
- keep packaging-track work limited to runtime reopening and oracle enablement
- continue static extraction, format recovery, and cross-branch integration in parallel

## What Would Reopen Route A

Any one of these is enough:

- the local Oracle VBox candidate becomes `adb-online` and accepts the original APK
- a third-party Android runtime on this host executes `armeabi-v7a` apps reliably
- a real ARM Android device becomes available
- a different emulator stack with working ARM guest support appears
