# AW2 Phase 0 Installability Gate

Audit date: 2026-04-03

## Scope

This note records the actual `Phase 0` result for the `AW2 feasibility-first packaging track`.

Target APK:

- `C:\vs\other\arelwars\arel_wars2\arel_wars_2.apk`

## APK Facts

From `aapt dump badging`:

- package: `com.gamevil.ArelWars2.global`
- version: `1.0.7` (`versionCode=107`)
- min SDK: `8`
- target SDK: `14`
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

Implication:

- AW2 is materially more feasible than AW1 because it includes `armeabi-v7a`.
- But it still does not provide `x86`, `x86_64`, or `arm64-v8a`.

## Install Attempts

### Attempt 1: Existing x86_64 AVD

Environment:

- AVD: `Medium_Phone_API_36.1`
- ABI: `x86_64`

Result:

- `adb install -r C:\vs\other\arelwars\arel_wars2\arel_wars_2.apk`
- failure:
  - `INSTALL_FAILED_NO_MATCHING_ABIS`
  - `Failed to extract native libraries, res=-113`

Conclusion:

- the existing x86_64 Google Play emulator cannot install the original APK directly

### Attempt 2: New ARMv7 AVD

Environment:

- installed system image: `system-images;android-23;google_apis;armeabi-v7a`
- created AVD: `AW2_ARMv7_API23`

Result:

- emulator fails before boot
- fatal message:
  - `CPU Architecture 'arm' is not supported by the QEMU2 emulator, (the classic engine is deprecated!)`

Conclusion:

- the current Android Emulator build cannot run a 32-bit ARM AVD on this host

### Attempt 3: New ARM64 AVD

Environment:

- installed system image: `system-images;android-23;google_apis;arm64-v8a`
- created AVD: `AW2_ARM64_API23`

Result:

- emulator fails before boot
- fatal message:
  - `QEMU2 emulator does not support arm64 CPU architecture`

Conclusion:

- the current Android Emulator build on this machine also cannot run an ARM64 AVD

## Verdict

`Phase 0 = no-go in the current environment`

Reason:

- original AW2 APK is present and well-formed
- but no locally runnable Android environment currently accepts its native ABI set

This is a stronger result than AW1:

- AW1 failed because the APK only shipped `armeabi`
- AW2 improves that to `armeabi-v7a`
- but the practical blocker remains the same on this machine because the available emulator stack is still not ARM-capable

## What Would Reopen The Track

One of the following external prerequisites is still required:

- a third-party Android runtime that can actually execute `armeabi-v7a` apps on this host
- a real ARM device
- a different emulator stack with ARM guest support

Until one of those exists, `AW2 original-equivalence / x64 packaging` remains blocked at `Phase 0`.
