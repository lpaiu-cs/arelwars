# AW2 Phase 5 Bootstrap Audit

Audit date: 2026-04-03

This note fixes the minimum bootstrap surface that an AW2 x64 runtime must replace.

Primary machine-readable source:

- [apk_runtime_audit.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/apk_runtime_audit.json)

## Original Bootstrap Chain

The original package entry is:

- `com.gamevil.ArelWars2.global.DRMLicensing`

The gameplay launcher chain behind that entry is:

- `DRMLicensing`
- `ArelWars2Launcher`
- `org.gamevil.CCGXNative.CCGXActivity`
- `org.cocos2dx.lib.Cocos2dxActivity`

Confirmed class hierarchy:

- `DRMLicensing -> com.gamevil.lib.GvDrmActivity`
- `ArelWars2Launcher -> org.gamevil.CCGXNative.CCGXActivity`
- `CCGXActivity -> org.cocos2dx.lib.Cocos2dxActivity`
- `NexusGLActivity -> com.gamevil.lib.GvActivity`

## Native Library Load Path

The decisive static loader is [CCGXActivity.java.bak](/C:/vs/other/arelwars/recovery/arel_wars2/apk_unzip/org/gamevil/CCGXNative/CCGXActivity.java.bak).

Its static initializer loads:

- `cocos2d`
- `cocosdenshion`
- `gameDSO`

The DEX audit confirms the same `System.loadLibrary(...)` pattern from:

- `Lorg/gamevil/CCGXNative/CCGXActivity;-><clinit>()V`

Additional native library loads also exist for:

- `openslaudio`
- `nativeinterface`

## GL / JNI Lifecycle Surface

Critical native bridge callers from the DEX audit:

- `NexusGLActivity.onGameResume -> Natives.InitializeJNIGlobalRef`
- `NexusGLRenderer.surfaceCreated -> Natives.NativeInitWithBufferSize`
- `NexusGLRenderer.surfaceChanged -> Natives.NativeResize`
- `NexusGLRenderer.drawFrame -> Natives.NativeRender`
- `NexusGLSurfaceView.onPause -> Natives.NativePauseClet`
- `NexusGLSurfaceView.onResume -> Natives.NativeResumeClet`

So the minimum x64 bootstrap must preserve:

- activity/bootstrap compatibility
- GL surface creation
- resize notifications
- frame render loop
- pause/resume lifecycle
- JNI ref initialization on resume

## Native Method Surface

The audit found:

- `71` native methods total
- `19` native methods under `com.gamevil.nexus2.Natives`
- top native-heavy classes:
  - `org.cocos2dx.lib.Cocos2dxActivity` = `21`
  - `com.gamevil.nexus2.Natives` = `19`
  - `org.cocos2dx.lib.Cocos2dxRenderer` = `12`
  - `org.gamevil.CCGXNative.CCGXNative` = `8`

Important `com.gamevil.nexus2.Natives` methods include:

- `InitializeJNIGlobalRef`
- `NativeInitDeviceInfo`
- `NativeInitWithBufferSize`
- `NativeRender`
- `NativeResize`
- `NativePauseClet`
- `NativeResumeClet`
- `NativeDestroyClet`
- `NativeHandleInAppBiiling`
- `NativeResponseIAP`
- `NativeAsyncTimerCallBack`
- `NativeAsyncTimerCallBackTimeStemp`
- `NativeNetTimeOut`
- `NativeIsNexusOne`
- `NativeGetPublicKey`
- `NativeGetPlayerName`
- `NativeUnLockItem`
- `handleCletEvent`
- `SetCletStarted`

## Current JNI Export Shape

Direct JNI export resolution by ARM ABI is:

- `59 / 71` direct matches on `armeabi`
- `59 / 71` direct matches on `armeabi-v7a`

The missing direct exports are concentrated in:

- `NativeGetPlayerName`
- `NativeUnLockItem`
- `NexusFont`
- Samsung `NativeInterface`
- SKT `ArmManager`
- `org.gamevil.CCGXNative.CCGXNative.ccgxNativeHandleCletEvent`

This strongly suggests AW2 still uses a mix of:

- direct `Java_*` exports
- non-direct registration / auxiliary native libraries

## Packaging Implication

The original APK ships only:

- `armeabi`
- `armeabi-v7a`

and does **not** ship:

- `x86`
- `x86_64`

So Phase 5 still needs a replacement runtime path.

The audit blocker list remains valid:

- no `lib/x86_64/*.so`
- Java hardcodes `System.loadLibrary("gameDSO")`
- render startup is still native
- current repo still has no AW2 Android build tree

## Concrete Phase 5 Output Target

The first AW2 x64 bootstrap should not try to solve gameplay yet.

It should only prove:

1. package/activity names are compatible with the original bootstrap chain
2. `gameDSO` replacement loading works on x64
3. the GL lifecycle reaches:
   - init
   - resize
   - render
4. oracle trace fields can be emitted beside that bootstrap

## Immediate Next Step

Create the first versioned AW2 x64 bootstrap tree and mirror the original package surface:

- `com.gamevil.ArelWars2.global`
- `org.gamevil.CCGXNative`
- `com.gamevil.nexus2`
- replacement native payload for `gameDSO`
