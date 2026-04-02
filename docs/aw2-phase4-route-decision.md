# AW2 Phase 4 Route Decision

Audit date: 2026-04-03

## Decision

- `Route C` selected
- label: `static reverse-engineering only`

## Why Route A Is Rejected

`Route A` requires the original AW2 APK to run in the current environment so that it can serve as a live oracle.

That is not true here:

- the original APK is present
- the existing `x86_64` AVD rejects it with `INSTALL_FAILED_NO_MATCHING_ABIS`
- the current Android Emulator build on this host cannot boot `ARMv7` guests
- the current Android Emulator build on this host cannot boot `ARM64` guests either

Therefore there is still no live original AW2 runtime on this machine.

## Why Route B Is Rejected

`Route B` would mean “the original package installs, but oracle evidence is weak.”

That is not the current situation.
The blocker is earlier than oracle weakness:

- the original package does not run at all in the available environment

So `Route B` would understate the blocker.

## Why Route C Is Correct

`Route C` matches the observed state:

- packaging work is blocked
- original-equivalence work is blocked
- static reverse-engineering remains productive and is already validated by [aw2-phase3-static-bootstrap-status.md](/C:/vs/other/arelwars/docs/aw2-phase3-static-bootstrap-status.md)

## Consequence

From this point:

- do not start `Phase 5` through `Phase 10`
- do not claim AW2 x64 packaging is in progress
- keep AW2 work limited to static extraction, format recovery, and cross-branch integration

## What Would Reopen Route A

Any one of these is enough:

- a third-party Android runtime on this host that can execute `armeabi-v7a` apps
- a real ARM Android device
- a different emulator stack with working ARM guest support
