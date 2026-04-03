# AW2 Phase 0 Installability Gate

Audit date: 2026-04-03

## Verdict

- `Phase 0 = go`

The original [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk) is now installable in the current environment.

## APK Facts

From `aapt dump badging`:

- package: `com.gamevil.ArelWars2.global`
- version: `1.0.7` (`versionCode=107`)
- launch activity: `com.gamevil.ArelWars2.global.DRMLicensing`
- native code: `armeabi`, `armeabi-v7a`

Embedded native libraries by ABI:

- `armeabi`
  - `libImmEmulatorJ.so`
  - `libcocos2d.so`
  - `libcocosdenshion.so`
  - `libgameDSO.so`
  - `libopenslaudio.so`
- `armeabi-v7a`
  - `libImmEmulatorJ.so`
  - `libcocos2d.so`
  - `libcocosdenshion.so`
  - `libgameDSO.so`
  - `libopenslaudio.so`

## Runtime That Passed

The approved install target is no longer the stock Android Emulator.

It is the reopened local `BlueStacks Nougat32` guest, reached through the installed BlueStacks runtime and the restored [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk) template path.

Current device facts:

- `adb serial = emulator-5554`
- `ro.product.cpu.abilist = x86,armeabi-v7a,armeabi`
- `ro.dalvik.vm.native.bridge = libnb.so`

## Install Evidence

The original package now installs successfully:

```powershell
adb -s emulator-5554 install -r C:\vs\other\arelwars\arel_wars2\arel_wars_2.apk
```

Manual package-path verification also succeeds:

```powershell
adb -s emulator-5554 shell pm path com.gamevil.ArelWars2.global
```

Resolved base path:

- `/data/app/com.gamevil.ArelWars2.global-1/base.apk`

Package identity is captured in:

- [probe-live-rerun.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/probe-live-rerun.json)

That probe records:

- `installedPackagePath != null`
- `installedMatchesExpectedApk = true`
- SHA-256 match against the original APK

## Consequence

The packaging track is no longer blocked at installability.

This moves AW2 from:

- `blocked before runtime`

to:

- `runtime/oracle enabled`

Phase 0 is therefore closed and Phase 1 / Phase 2 can proceed on the live original package.
