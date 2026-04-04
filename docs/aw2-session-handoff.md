# AW2 Session Handoff

Audit date: 2026-04-04

## Goal

Current goal is **original AW2 offline-hook progression + native-equivalent reverse engineering**, not a forced fake port.

The immediate objective is:

1. keep the original `arel_wars_2.apk` runnable without dead-server blockers
2. preserve the native state machine as much as possible
3. reopen real worldmap -> stage-select progression without direct `CreateStageSelect` forcing
4. keep documenting every closed branch so a new session can continue without rediscovering the same structure

## Current Live State

The offline-hook build has progressed far enough that the user manually reached the in-game worldmap.

Current live behavior:

- startup network blockers are no longer the main stopper
- `Town SHOP` responds and causes visible UI motion
- generic base worldmap objects such as `DESERT PLAIN` and `PVP` still do **not** respond

Interpretation:

- the overlay/button layer is alive
- the generic base-area path is still blocked or geometrically misaligned

## What Has Already Been Solved

The dead-server startup path was substantially cut down in the offline-hook APK builder:

- live/news/gift/tapjoy/network bootstrap gates were bypassed
- terms / abnormal-file / launcher-edge blockers were reduced
- `openUrl` was no-op patched to avoid store / external jump behavior

The active builder is:

- [build_aw2_offline_hook_apk.py](/C:/vs/other/arelwars/tools/arel_wars2/build_aw2_offline_hook_apk.py)

The main live-analysis document is:

- [aw2-worldmap-input-analysis.md](/C:/vs/other/arelwars/docs/aw2-worldmap-input-analysis.md)

Useful generated reports:

- [aw2_worldmap_hit_result_accesses.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_hit_result_accesses.json)
- [aw2_worldmap_selection_flow.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_selection_flow.json)
- [aw2_worldmap_area_state_flow.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_area_state_flow.json)
- [aw2_worldmap_input_flags.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_input_flags.json)
- [aw2_worldmap_flag_accesses.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_flag_accesses.json)

## Unsafe Approaches That Are Now Out Of Bounds

Do **not** reintroduce these as default fixes:

- `TouchInputWorldMapMenu -> CreateStageSelect`
- `Select_WorldMapMain -> CreateStageSelect`
- `TouchInputGamestart -> CreateStageSelect`
- `TouchInputStageSelect -> CreateStageInfo`
- `TouchInputStageInfo -> CreateGameStart`
- blind `OnPointerPress` guard `nop` patches
- blind branch forcing inside `UpdateWorldMapMenu`

Reason:

- these bypass the real worldmap state machine
- they desynchronize input latches, pending-state fields, and scene ownership
- earlier experiments showed they can assert the same gate bytes that later block touch handling

## Closed Static Truth

### 1. `OnPointerPress` is a latch writer, not the transition owner

`CPdStateWorldmap::OnPointerPress(GxPointerPos*)`:

- checks `global + 0x1068`
- stores touch coordinates into the worldmap object
- sets press flags
- writes `1` to the shared latch `global + 0x58`

So press is just preparing later handlers.

### 2. `DrawLoading` owns real scene creation

Confirmed from [aw2_worldmap_state_tables.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_state_tables.json):

- `[this+0x34] == 4` -> `CreateStageSelect`
- `[this+0x34] == 5` -> `CreateStageInfo`
- `[this+0x34] == 17` -> `CreateGameStart`

So release-time code is not supposed to jump directly into these scene creators.

### 3. `0x200` is not a base-area index

This was an important correction.

`CPdStateWorldmap::TouchInputWorldFrame(int, int)`:

- calls `CCommonUI::TouchInputWorldFrame(...)`
- stores its result into `[this+0x200]`

`CCommonUI::TouchInputWorldFrame(...)`:

- only ORs `CPdSharing::ClickButtonIcon(...)` hits across up to four icon pointers

`CPdStateWorldmap::DoTouchMoveWorldArea(int, int)`:

- reads `[this+0x200]`
- if it is nonzero, clears it and returns **before** the generic world-area scan

Therefore:

- `0x200` is an overlay/button-layer hit latch
- it is **not** the generic world-area candidate

This is the strongest explanation for why `Town SHOP` works while `DESERT PLAIN` and `PVP` do not.

### 4. Generic base-area selection is a separate flow

Inside `DoTouchMoveWorldArea(...)`:

- new generic area hit -> store candidate into `[this+0x100]`
- then call `InitWorldmapSltAreaAni(...)`
- only a **same-area re-tap** reaches `IsCheckAreaEnter(...)`
- if enterable:
  - set `[this+0x379c] = 1`
  - copy `[this+0x100] -> [this+0x36f8]`
- later `UpdateWorldMapMenu(...)` consumes `0x36f8`
  - `0..4` -> mirror to `0x361c`, set pending state `[this+8] = 2`
  - `5` -> pending state `[this+8] = 0x19`

This means the generic area path is:

`hit -> select area -> same-area re-tap -> arm 0x36f8 -> UpdateWorldMapMenu -> state 2 -> later loading`

### 5. `Town SHOP` likely corresponds to the special `area == 5` branch

`IsCheckAreaEnter(...)`:

- `area == 5` returns true immediately
- normal areas require `globalProgress24 >= areaIndex * 15`

This matches the live observation:

- special `Town SHOP`-style branch can react
- generic `0..4` areas still fail

### 6. Generic area hit-testing is bounding-box driven

Another important closure:

- `DoTouchMoveWorldArea(...)` does **not** use a simple static screen-rectangle table
- it resolves the active worldmap frame from `this + 0xe0`
- it enumerates bounding boxes from that frame
- relevant helpers are:
  - `CGxPZxFrame::GetBoundingBoxCount(...)`
  - `CGxPZxFrame::GetBoundingBox(...)`
- it also reads offset/camera-style values from `this + 0xdc` before comparing pointer coordinates

Implication:

- generic world-area failure may be a geometry / translation mismatch
- not just a stale state gate

### 7. `TouchGamevilLiveBtns(...)` is a pre-area swallow path

Before generic area scanning, `DoTouchMoveWorldArea(...)` calls `TouchGamevilLiveBtns(x, y)`.

If that helper returns nonzero, the generic area path is skipped.

Closed early-return guards inside `TouchGamevilLiveBtns(...)`:

1. `global + 0x1068 != 0`
2. `this + 0x36f0 != -1`

`0x36f0` looks like a stale live-button / overlay slot:

- `DrawGamevilLiveBtns(...)` reset path writes `-1`
- `OnNetError(...)` writes `1` in one branch
- `SelectNetFriendList(...)` also manipulates nearby state

Current targeted patch in the builder:

- `native-worldmap-ignore-stale-live-button-gate`

This is a constrained stale-slot bypass, not a direct scene jump.

## Current Patch Posture

The current builder intentionally keeps only lower-risk worldmap patches:

- tap slop widening on release-time delta checks
- `UpdateMainLoop` slot alignment patch
- stale `0x36f0` live-button gate bypass

It explicitly avoids:

- direct scene-creation jumps
- blind `OnPointerPress` / `UpdateWorldMapMenu` state smashing
- worldmap-local `OnNetError` / `OnNetReceive` no-op cutting when that appeared to remove cleanup

## Most Likely Remaining Blockers

At this point the live failure is narrowed to one or more of these:

1. generic area hitboxes are present, but their translated coordinates no longer match the visible world objects
2. `[this+0x100]` is not changing on first base-area hit
3. same-area re-tap is not arming `[this+0x379c] / [this+0x36f8]`
4. `UpdateWorldMapMenu(...)` is not consuming the armed pending area into `state 2`
5. `TouchGamevilLiveBtns(...)` still swallows some releases before the generic scan

## Best Next Steps For A New Session

1. Do **not** start by adding more force-jump patches.
2. Rebuild and reinstall from the current builder.
3. Keep [aw2-worldmap-input-analysis.md](/C:/vs/other/arelwars/docs/aw2-worldmap-input-analysis.md) updated as each new branch closes.
4. Focus on the generic area path:
   - verify whether `[this+0x100]` is seeded and then updated on touch
   - verify whether generic bounding boxes from the active frame line up with the visible worldmap art
   - verify whether `state 2` is actually reached after `UpdateWorldMapMenu`
5. Treat `Town SHOP` only as proof that the overlay path is alive, not as proof that base-map interaction is healthy.

## Build / Reinstall Reminder

Use a clean install when testing behavior changes:

```powershell
adb uninstall com.gamevil.ArelWars2.global
python C:\vs\other\arelwars\tools\arel_wars2\build_aw2_offline_hook_apk.py --apk C:\vs\other\arelwars\arel_wars2\arel_wars_2.apk --device emulator-5554 --install
