# AW1 Asset / Save Passthrough

## Goal

Phase 7 switches the translation path away from parser-owned runtime data and toward opaque passthrough inputs:

- original asset bytes should remain available as shipped
- runtime save state should persist as opaque blob files
- `PZX/PZD/PZF/PZA/MPL/PTC/ZT1` parsers remain for preview / interpretation / verification only

## In-app x86_64 Shim Changes

Android project:

- wrapper entry: `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/cpp/arm_runner_wrapper.h`
- wrapper implementation: `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/cpp/arm_runner_wrapper.cpp`
- JNI bridge: `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/cpp/game_dso.cpp`
- Java bridge: `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/java/com/gamevil/nexus2/Natives.java`
- save store: `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/java/com/gamevil/eruelwars/global/Aw1SaveStore.java`
- activity integration: `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/java/com/gamevil/eruelwars/global/MainActivity.java`
- packaging: `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/build.gradle.kts`

### Asset passthrough

The debug/release APK now packages two ARM-runner assets:

- `assets/arm_runner/libgameDSO.so`
- `assets/arm_runner/arel_wars_1.apk`

`ArmRunnerWrapper` loads and validates both:

- ARM payload: original `ELF32 / EM_ARM` game library
- original APK container: zip-header-checked raw source archive for exact shipped asset bytes

The wrapper records JNI export count, `DT_NEEDED` count, original APK byte size, and original APK `crc32`.

### Save passthrough

`Aw1SaveStore` no longer stores runtime state in `SharedPreferences` JSON. It now writes opaque binary blobs:

- autosave: `files/arm_runner_passthrough/autosave.aw1sav`
- slots: `files/arm_runner_passthrough/slot_<n>.aw1sav`

`MainActivity` mirrors each autosave / slot save through `NativeCommitPassthroughSave(...)`, and `ArmRunnerWrapper` writes the same opaque blob into the app-private passthrough directory. This is the save payload intended for the future ARM runner path.

The current blob format is a wrapper-owned opaque transport container, not a final claim about the original ARM save layout.

## Validation

Build:

- `C:/Users/lpaiu/AndroidStudioProjects/arelwars1/gradlew.bat assembleDebug`

APK contents confirmed:

- `lib/x86_64/libgameDSO.so`
- `assets/arm_runner/libgameDSO.so`
- `assets/arm_runner/arel_wars_1.apk`

Runtime evidence from `adb logcat`:

- `AttachAssetManager:passthrough-assets-ready`
- `AttachWritableRoot:ready`
- `CommitPassthroughSave:ok`

Observed wrapper state:

- `armAsset=1`
- `valid=1`
- `elf32=1`
- `arm=1`
- `apkAsset=1`
- `apkValid=1`
- `apkBytes=12568874`
- `apkCrc32=ff881011`
- `saveRoot=1`
- `saveDir=1`
- `saveCommits=1`

## Scope Boundary

This phase does not mean the ARM engine is already executing in-app. It means the in-app x86_64 shim now owns:

- the original ARM library payload
- the original APK asset container
- opaque runtime save blobs

and the fallback preview/runtime path no longer needs to be treated as the authoritative source of runtime asset/save data.
