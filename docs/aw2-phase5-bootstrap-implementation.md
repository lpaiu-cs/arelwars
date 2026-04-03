# AW2 Phase 5 Bootstrap Implementation

Audit date: 2026-04-03

This note records the first repo-contained AW2 Android bootstrap project and the first live install proof.

## Project

The new project lives under:

- [ports/arelwars2-android](/C:/vs/other/arelwars/ports/arelwars2-android)

It is no longer dependent on the external AW1 Android Studio tree.

Key implementation points:

- package/class surface mirrors the original bootstrap chain:
  - `com.gamevil.ArelWars2.global.DRMLicensing`
  - `com.gamevil.ArelWars2.global.ArelWars2Launcher`
  - `org.gamevil.CCGXNative.CCGXActivity`
  - `org.cocos2dx.lib.Cocos2dxActivity`
  - `com.gamevil.nexus2.NexusGLActivity`
- replacement native libraries are built for:
  - `x86`
  - `x86_64`
- replacement library names match the original load path:
  - `libcocos2d.so`
  - `libcocosdenshion.so`
  - `libopenslaudio.so`
  - `libgameDSO.so`
- the original AW2 assets are packaged directly from:
  - [apk_unzip/assets](/C:/vs/other/arelwars/recovery/arel_wars2/apk_unzip/assets)
- the original APK and ARM payloads are also embedded as pass-through assets:
  - `assets/arm_runner/arel_wars_2.apk`
  - `assets/arm_runner/libgameDSO.so`
  - `assets/arm_runner/libcocos2d.so`
  - `assets/arm_runner/libcocosdenshion.so`
  - `assets/arm_runner/libopenslaudio.so`

## Build Proof

Build command:

- `./gradlew.bat assembleDebug`

Produced artifact:

- [app-debug.apk](/C:/vs/other/arelwars/ports/arelwars2-android/app/build/outputs/apk/debug/app-debug.apk)

Badging proof:

- [aw2-bootstrap-debug-badging.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-debug-badging.txt)

Important facts from the built debug APK:

- installed package id is `com.gamevil.ArelWars2.global.bootstrap`
- launch activity remains `com.gamevil.ArelWars2.global.DRMLicensing`
- native code shipped:
  - `x86`
  - `x86_64`

The debug package id uses a suffix on purpose so the bootstrap shell can coexist with the original oracle package on the same emulator.

## Live Install Proof

Device:

- `adb -s emulator-5554`

Install command:

- `adb -s emulator-5554 install -r ...\\app-debug.apk`

Launch command:

- `adb -s emulator-5554 shell am start -W -n com.gamevil.ArelWars2.global.bootstrap/com.gamevil.ArelWars2.global.DRMLicensing`

Observed runtime result:

- launcher activity starts successfully
- bootstrap auto-advances to `ArelWars2Launcher`
- GL surface initializes
- first render occurs

Evidence:

- screenshot: [aw2-bootstrap-debug.png](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-debug.png)
- UI dump: [aw2-bootstrap-debug-ui.xml](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-debug-ui.xml)
- activity state: [aw2-bootstrap-debug-activity.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-debug-activity.txt)
- logcat: [aw2-bootstrap-debug-logcat.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-debug-logcat.txt)

The current UI dump shows:

- resumed activity is `ArelWars2Launcher`
- runtime status text reports `publicKey=aw2-bootstrap:surface:started:frames=162`

The current logcat shows:

- `JNI_OnLoad`
- `SetCletStarted=true`
- `InitializeJNIGlobalRef`
- `NativeInitWithBufferSize`
- `NativeRender:first-frame`

## Phase 5 Status

This is enough to say:

- the repo-contained bootstrap project exists
- the replacement runtime loads and runs live
- the original bootstrap class chain is mirrored
- the runtime is instrumentable

But one restriction remains:

- the live oracle emulator is `x86`, not `x86_64`

So the precise status is:

- `Phase 5 baseline implemented`
- `Phase 5 live bootstrap proven on x86`
- `x86_64 payload is built and packaged, but not yet live-executed on an x86_64 Android runtime`

