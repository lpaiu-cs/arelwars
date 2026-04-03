# AW2 Phase 5 To Phase 10 Status

Audit date: 2026-04-03

## Result

- `Phase 5 = reopened, not yet completed`
- `Phase 6 = reopened, not yet completed`
- `Phase 7 = reopened, not yet completed`
- `Phase 8 = reopened, not yet completed`
- `Phase 9 = reopened, not yet completed`
- `Phase 10 = reopened, not yet completed`

## What Changed

These phases were previously blocked because no live original-runtime oracle existed on this machine.

That blocker is gone.

The current environment now has:

- live `adb` device `emulator-5554`
- successful install of the original [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk)
- successful launch of `com.gamevil.ArelWars2.global/.DRMLicensing`
- a working oracle probe and capture harness

Reference evidence:

- [probe-live-rerun.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/probe-live-rerun.json)
- [live-drm-smoke-v4/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/session.json)
- [jni_profile.prof](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/artifacts/jni_profile.prof)

## What Is Still Not Done

Reopened does not mean completed.

The remaining work is still substantial:

- Phase 5: x64 runtime bootstrap for AW2 does not exist yet
- Phase 6: x64 trace schema parity does not exist yet
- Phase 7: no representative original-vs-x64 equivalence pass has been run
- Phase 8: no save/load or lifecycle equivalence report exists yet
- Phase 9: no AW2 differential suite has been passed yet
- Phase 10: no approved signed final x64 AW2 APK exists yet

## Practical Meaning

From the packaging-track perspective:

- do start x64 bootstrap work
- do use the live original runtime as the oracle
- do not claim equivalence or final packaging yet
- do not treat any provisional APK as a certified final artifact

## Immediate Next Phase

The next approved implementation step is:

- `Phase 5` AW2 x64 runtime bootstrap
