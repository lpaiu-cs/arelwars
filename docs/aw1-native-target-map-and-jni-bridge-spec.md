# AW1 Native Target Map And JNI Bridge Spec

Audit date: 2026-04-02

This document fixes two things for the next reverse-engineering phases:

1. the original `18`-entry JNI bridge surface that must be preserved for oracle-equivalent execution
2. the native target map that should be traced first, based on the latest `main` outputs and current `disassemble` findings

The matching machine-readable export lives at:

- [aw1_native_target_map.json](/C:/vs/other/arelwars/recovery/arel_wars1/aw1_native_target_map.json)

## Source Inputs

Original JNI surface:

- [apk_runtime_audit.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/apk_runtime_audit.json)
- [libgameDSO.so](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/libgameDSO.so)
- [Natives.java](/C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/java/com/gamevil/nexus2/Natives.java)

Latest `main`-side search hints:

- `origin/main:recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json`
- `origin/main:recovery/arel_wars1/parsed_tables/AW1.engine_schema.json`
- `origin/main:recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json`
- [aw1-main-branch-disassemble-integration.md](/C:/vs/other/arelwars/docs/aw1-main-branch-disassemble-integration.md)

## Oracle JNI Surface

The oracle bridge is the original DEX-declared `18`-entry surface, not the current Android-port helper surface.

Current Android Studio project delta:

- [Natives.java](/C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/src/main/java/com/gamevil/nexus2/Natives.java) currently declares `23` native methods total.
- Of these, `18` belong to the original oracle surface.
- The remaining five are port-only helpers:
  - `NativeApplySettings`
  - `NativeRestoreSession`
  - `NativeTouchEvent`
  - `NativeAttachAssetManager`
  - `NativeSetPreviewAsset`

These are useful for the port, but they are not part of the original oracle bridge and must not be treated as required ABI for original-equivalent execution.

## Original 18-Entry Bridge Table

| Method | Descriptor | Java Callers | Bridge Role | Direct ARM Export | Notes |
| --- | --- | --- | --- | --- | --- |
| `InitializeJNIGlobalRef` | `()V` | `NexusGLActivity.onResume()` | JVM/native global-ref init at activity resume | `yes` | Treat as startup bridge and possible registration/setup point. |
| `NativeAsyncTimerCallBack` | `(I)V` | `NativesAsyncTask.onPostExecute(Integer)` | async timer callback without timestamp | `yes` | Native timer/event queue ingress. |
| `NativeAsyncTimerCallBackTimeStemp` | `(I I)V` | `NativesAsyncTask.onPostExecute(Integer)` | async timer callback with timestamp | `yes` | Same callback family, richer timing payload. |
| `NativeDestroyClet` | `()V` | `NexusGLActivity.onDestroy()` | lifecycle destroy | `yes` | Hard shutdown path. |
| `NativeGetPlayerName` | `(Ljava/lang/String;)V` | none found in current DEX xref | player-name / profile bridge | `no direct export seen` | Needs `JNI_OnLoad`/hidden binding confirmation or dead-surface confirmation. |
| `NativeGetPublicKey` | `()Ljava/lang/String;` | `Security.verifyPurchase(String,String)` | purchase verification/public-key source | `yes` | Security/IAP bridge. |
| `NativeHandleInAppBiiling` | `(Ljava/lang/String; I I)V` | `SkeletonLauncher$Nexus2PurchaseObserver.onPurchaseChange(...)`, `onRequestPurchaseCallback(...)` | Java purchase observer -> native billing event | `yes` | Preserve spelling mismatch as-is. |
| `NativeInitDeviceInfo` | `(I I)V` | `NexusGLRenderer.surfaceChanged(GL10,int,int)` | device/surface dimension handoff | `yes` | Pairs with resize path. |
| `NativeInitWithBufferSize` | `(I I)V` | `NexusGLRenderer.surfaceCreated(GL10)` | GL/native initialization | `yes` | First hard render bootstrap target. |
| `NativeIsNexusOne` | `(Z)V` | `eruelwarsUIControllerView.onInitialize()` | device-quirk flag | `yes` | Small but still original bridge surface. |
| `NativeNetTimeOut` | `()V` | none found in current DEX xref | network timeout notification | `yes` | Likely sparse or dormant in normal local runs. |
| `NativePauseClet` | `()V` | `NexusGLSurfaceView.onPause()` | lifecycle pause | `yes` | Required for lifecycle equivalence. |
| `NativeRender` | `()V` | `NexusGLRenderer.drawFrame(GL10)` | per-frame render tick | `yes` | Highest-frequency JNI bridge. |
| `NativeResize` | `(I I)V` | `NexusGLRenderer.surfaceChanged(GL10,int,int)` | surface resize/update | `yes` | Window/orientation bridge. |
| `NativeResponseIAP` | `(Ljava/lang/String; I)V` | none found in current DEX xref | purchase response bridge | `yes` | Still part of oracle surface even if sparse. |
| `NativeResumeClet` | `()V` | `NexusGLSurfaceView.onResume()` | lifecycle resume | `yes` | Required for lifecycle equivalence. |
| `NativeUnLockItem` | `(I I)I` | none found in current DEX xref | unlock/item progression bridge | `no direct export seen` | Needs `JNI_OnLoad`/hidden binding confirmation or dead-surface confirmation. |
| `handleCletEvent` | `(I I I I)V` | `SkeletonLauncher$2.onClick(View)`, `SkeletonLauncher.getTapjoyGPoint()`, `UIFullTouch.onAction(...)`, `Natives$8$1.onClick(...)`, `NexusGLRenderer.sendHandleCletEvent()`, `NexusTouch$GestureListener.onFling(...)`, `NexusTouch.onDoubleTap(...)`, `UIEditNumber.onEditorAction(...)`, `UIEditNumber.onKeyDown(...)`, `UIEditText.closeInput()`, `UIEditText.onEditorAction(...)`, `UIEditText.onKeyDown(...)` | generic UI/input/event bridge | `yes` | Broadest Java->native command path. |

## Bridge Interpretation Rules

1. The original bridge surface is fixed to these `18` methods.
2. For oracle-equivalent execution, extra helper JNI in the current port is optional and must stay outside the required bridge.
3. `NativeGetPlayerName` and `NativeUnLockItem` remain bridge-resolution targets because:
   - the original DEX declares them as native
   - the current ELF export audit does not show direct `Java_*` symbols for them
   - no `RegisterNatives` proof has been closed yet on `disassemble`
4. Until that closes, these two methods are classified as:
   - `bridge-unresolved`

## Native Target Map

### 1. Stage bootstrap and map binding

Primary search target:

- the native path that turns script/story selection into `XlsAi` row selection and then concrete map selection

Latest exact signals from `main`:

- `script family id == XlsAi row index`
- `XlsAi numericBlock byte[15] -> pairBaseIndex`
- `XlsAi numericBlock byte[18] -> pairBranchIndex`
- `preferredMapIndex = pairBaseIndex + pairBranchIndex`
- coverage on `main`: `111/111`

Why this is first:

- it anchors stage identity
- it anchors map identity
- it is required by the equivalence gates fixed in Phase 1

Disassemble-side search focus:

- stage loader
- story bootstrap / script family selector
- `XlsAi` row materialization
- map-pair / branch-bit consumer

### 2. Fixed runtime-table loaders

Primary `main`-derived table targets:

- `XlsHero_Ai`
- `XlsSkill_Ai`
- `XlsProjectile`
- `XlsEffect`
- `XlsParticle`

Current row counts from the latest schema export:

- `Hero_Ai = 12`
- `Skill_Ai = 24`
- `Projectile = 35`
- `Effect = 37`
- `Particle = 12`

Why this is second:

- these are compact, fixed-layout tables
- they are good candidates for recognizable native loader loops
- battle/runtime equivalence will depend on them even if asset parsing is already closed

Disassemble-side search focus:

- GXL table-open paths
- repeated allocation/copy loops matching `12`, `24`, `35`, `37`
- cached battle-definition objects populated from `data_eng/*.zt1` or `data_kor/*.zt1`

### 3. Hero active tail -> projectile/effect/PTC bridge

Latest exact signals from `main`:

- `XlsParticle` primary `PTC` direct hits: `12/12`
- `XlsParticle` nonzero secondary `PTC` direct hits: `10/10`
- shared primary `PTC 048` suggests a reusable emitter template
- `XlsHeroActiveSkill.tailPairBE` exact hits already include:
  - `(4, 1) -> projectile row 5`
  - `(3, 2) -> effect row 26`
  - `(3, 0) -> projectile row 4`
  - `(3, 0) -> effect row 24`

Why this is third:

- it is the strongest current bridge from skill tables to actual runtime spawns/effects
- it narrows projectile/effect/PTC launch tracing to a handful of concrete pair signatures

Disassemble-side search focus:

- hero active-skill consumer
- projectile spawn path
- effect spawn path
- `PTC` bridge table consumer

### 4. Script VM tutorial/UI family

High-priority opcode cluster:

- `cmd-00(0x0d)`
- `cmd-06(0x0d)`
- `cmd-07..0e(0x40)`

Why it stays high:

- it is the best current target for tutorial/HUD focus consumers
- it provides stable regression needles for script VM tracing

Disassemble-side search focus:

- script VM dispatch
- UI target/highlight consumers
- tutorial overlay or scene-focus presets

## Immediate Tracing Order

1. Close the native stage bootstrap path:
   - prove or reject `script family == XlsAi row`
   - prove or reject `numericBlock[15]` as map-pair selector
   - prove or reject `numericBlock[18]` as branch bit
2. Close the fixed GXL battle/runtime table loaders:
   - `Hero_Ai`
   - `Skill_Ai`
   - `Projectile`
   - `Effect`
   - `Particle`
3. Follow hero active-skill tail consumers into projectile/effect/PTC launch code.
4. Trace the `0x40` tutorial/UI family in the script VM.
5. Resolve the two JNI bridge-unresolved methods:
   - `NativeGetPlayerName`
   - `NativeUnLockItem`

## Approval For Phase 3

Phase 3 is approved only when:

1. the original `18` JNI entries are fixed in a document and machine-readable spec
2. the extra port-only JNI helpers are explicitly excluded from the oracle surface
3. the native target map includes at least:
   - `script family == XlsAi row`
   - `numericBlock byte[15]`
   - `numericBlock byte[18]`
   - `Hero_Ai / Skill_Ai / Projectile / Effect / Particle`
   - `hero active tail -> projectile/effect/PTC`
4. the tracing order is explicit enough that later phases can act on it without reinterpretation
