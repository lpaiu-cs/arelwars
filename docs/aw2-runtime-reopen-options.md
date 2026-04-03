# AW2 Runtime Reopen Options

Audit date: 2026-04-03

## Current Situation

The reopen task is no longer theoretical.

The local `BlueStacks Nougat32` path is now the approved runtime, not merely a candidate.

What is now proven:

- the restored [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk) template boots to a live guest
- official `adb` sees `emulator-5554` as `device`
- the original [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk) installs successfully
- the original process launches successfully
- oracle capture artifacts can be produced locally

## Approved Runtime Path

The currently approved path is:

- installed BlueStacks runtime
- `Nougat32` instance
- repo-backed [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk) restored from template
- original APK launched inside the live guest

This is the path that reopened the packaging track.

Primary evidence:

- [aw2-phase0-installability-gate.md](/C:/vs/other/arelwars/docs/aw2-phase0-installability-gate.md)
- [aw2-phase1-phase2-oracle-status.md](/C:/vs/other/arelwars/docs/aw2-phase1-phase2-oracle-status.md)
- [probe-live-rerun.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/probe-live-rerun.json)
- [live-drm-smoke-v4/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/session.json)

## What The Runtime Can Do Now

- boot the guest reproducibly
- expose a live `adb` target
- resolve package identity against the original APK
- launch `com.gamevil.ArelWars2.global/.DRMLicensing`
- collect screenshots, UI XML, frame hashes, logcat, scene focus, and profiler artifacts

Important captured artifacts:

- [aw2-current.xml](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/aw2-current.xml)
- [jni_profile.prof](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/artifacts/jni_profile.prof)

## What Still Matters

The reopen problem itself is solved, but the runtime is still only at early-scene oracle level.

Open work remains:

- move from `DRMLicensing` into later gameplay-relevant scenes
- identify where save roots appear in this runtime
- capture scenario-level oracle traces beyond bootstrap
- start the x64 bootstrap and parity work that this runtime now enables

## Fallbacks

The raw Oracle VBox-only route is now secondary.

It remains useful for low-level experiments, but it is no longer the leading reopen path because the installed BlueStacks route already crossed the threshold that mattered:

- `live original-runtime oracle on this machine`

## Immediate Consequence

Do not spend more time trying to prove that a reopen path exists.

That question is answered.

Spend time on:

- Phase 5 x64 bootstrap
- deeper oracle captures
- schema alignment and equivalence work
