# AW2 Phase 1 / Phase 2 Oracle Status

Audit date: 2026-04-03

## Result

- `Phase 1 = approved`
- `Phase 2 = approved`

## What Changed

The reopened `BlueStacks Nougat32` runtime crossed the earlier blocker line:

- guest is now `adb device`, not `offline`
- the original [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk) installs successfully
- the original process launches successfully
- the oracle harness now captures package identity, screenshots, UI, scene focus, audio snapshots, save roots, and profiler artifacts

The approved live device is:

- `serial = emulator-5554`
- `abiList = x86, armeabi-v7a, armeabi`
- `nativeBridge = libnb.so`

## Phase 1 Evidence

The original app now launches into a stable observable scene.

Explicit launch:

```powershell
adb -s emulator-5554 shell am start -W -n com.gamevil.ArelWars2.global/com.gamevil.ArelWars2.global.DRMLicensing
```

Observed runtime facts:

- focused component: `com.gamevil.ArelWars2.global/.DRMLicensing`
- UI dump contains the DRM terms WebView and `V9-IDC-v2.1.3`
- the process is visible in `dumpsys activity`
- BlueStacks logs show the guest reaches `Player state: ready`
- the original app can now be driven through DRM into `com.gamevil.ArelWars2.global/.ArelWars2Launcher`
- the first post-DRM observable scene is a `Network Error` modal owned by the launcher

Artifacts:

- [aw2-current.xml](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/aw2-current.xml)
- [live-drm-smoke-v4/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/session.json)
- [live-drm-smoke-v4/logcat.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/logcat.txt)
- [first-scene-v1/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/session.json)
- [05_post_start.xml](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/05_post_start.xml)
- [05_post_start.png](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/05_post_start.png)

So `Phase 1` is no longer “candidate runtime only.” It is a live original-runtime oracle.

## Phase 2 Evidence

The capture backend is now strong enough to drive equivalence work.

Current oracle session:

- [live-drm-smoke-v4/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/session.json)

That session proves:

- `installedMatchesExpectedApk = true`
- screenshot/frame hash capture works
- UI XML capture works
- scene transition capture works
- profiler artifact capture works
- package launch info is recorded

Most important profiler artifacts:

- [probe-live-rerun.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/probe-live-rerun.json)
  - `jniTraceBackendSatisfied = true`
  - probe artifact size `3529`
- [jni_profile.prof](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/live-drm-smoke-v4/artifacts/jni_profile.prof)
  - size `36217`
  - SHA-256 `e13e1df3db98d99cabbf31668547bcd543779a54b1f4b16e8785f5ad1b64ce14`

Current limitations are now secondary, not blocking:

- `run-as = unavailable`
- `su = unavailable`
- external save roots have not appeared yet on the DRM screen
- the current oracle boundary is launcher/bootstrap and first-scene network failure, not battle/menu
- the remote service behind the launcher `Network Error` dialog is outside the current packaged runtime graph

Those do not block Phase 2 approval because the required oracle schema can already be emitted by the live original runtime.

## Immediate Consequence

The AW2 packaging track is no longer blocked by missing original-runtime oracle support.

From this point:

- `Route A` is reopened
- phase work may continue into x64 runtime bootstrap and trace alignment
- `Phase 5` through `Phase 10` are no longer globally blocked by environment absence
- the live oracle may be treated as valid through the launcher/network-error boundary while network dependency is handled as an external scope item
