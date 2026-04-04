# AW2 Worldmap Input Analysis

Audit date: 2026-04-04

## Direction Change

The previous worldmap workaround path mixed up control-flow forcing with real state transition.

These patches are no longer treated as valid default progression fixes:

- `TouchInputWorldMapMenu -> CreateStageSelect`
- `Select_WorldMapMain -> CreateStageSelect`
- `TouchInputGamestart -> CreateStageSelect`
- `TouchInputStageSelect -> CreateStageInfo`
- `TouchInputStageInfo -> CreateGameStart`
- `OnPointerPress` early `bne` removal at `+0x1c`

They are unsafe because they bypass the worldmap state machine instead of fixing the state that blocks input.

## Confirmed Input Structure

`CPdStateWorldmap::OnPointerPress(GxPointerPos*)` begins with an early global-byte guard:

```asm
eb16a: ldr  r3, [r5, r3]
eb16c: ldr  r2, [r3]
eb170: ldrb r3, [r2, #0x1068]
eb172: cmp  r3, #0
eb174: bne  early_return
```

If that guard passes, the function:

- copies touch coordinates into `this+0xec .. this+0xf6`
- sets `this+0xfc = 1`
- sets `this+0xfd = 1`
- writes `1` to a shared global latch byte at offset `+0x58`

That means `OnPointerPress` is not directly advancing state. It latches touch data for later worldmap input handlers.

## Key Fields

The current literal scan of the original `libgameDSO.so` shows these fields are the most relevant:

- `global + 0x1068`
  - shared input/render gate, used by `CPdScriptMgr`, `CPdStateGame`, and multiple worldmap draw/touch paths
- `this + 0x379c`
  - worldmap-local flag used by `DrawStageSelect`, `DrawTownMenu`, `DrawNetMenu`, `TouchInputStageSelect`
  - zeroed during `CreateMainLoop`
- `this + 0x362c`
  - worldmap-local commit/dirty flag consumed by `TouchInputWorldMapMenu`, `TouchInputStageSelect`, `TouchInputStageInfo`, and many popup/menu flows
  - zeroed during both `CreateMainLoop` and `Initialize`
- shared latch byte `global + 0x58`
  - written by `OnPointerPress`
  - consumed by `TouchInputMainLoop`, `TouchInputWorldMapMenu`, `TouchInputStageSelect`

## Concrete Worldmap Flow

`TouchInputWorldMapMenu` checks, in order:

1. `global + 0x1068 == 0`
2. `this + 0x379c == 0`
3. shared latch byte `global + 0x58 != 0`
4. if so, it clears the shared latch byte
5. if `this + 0x362c != 0`, it clears `this + 0x362c`

`TouchInputStageSelect` follows the same structure:

1. `global + 0x1068 == 0`
2. `this + 0x379c == 0`
3. shared latch byte `global + 0x58 != 0`
4. clear shared latch
5. require `this + 0x362c == 0` before proceeding deeper into stage hit-testing

`DrawStageSelect` also checks both:

- `global + 0x1068`
- `this + 0x379c`

That makes the current bottleneck clear: the real issue is not “tap reaches Java but not native” in a generic sense. The issue is that one of the input gates remains asserted when worldmap should be interactive.

## Additional April 4 Findings

`UpdateWorldMapMenu` was traced again with Capstone around the previously patched branch. The earlier fallback patch that forced the branch at `+0x106` is now confirmed unsafe.

The original branch body does this before it rejoins the normal update flow:

```asm
10b7e8: ldr  r3, [pc, ...]    ; 0x36f8
10b7ea: ldr  r3, [r4, r3]
10b7ec: adds r3, #1
10b7ee: beq  skip
10b7f0: ldr  r2, [pc, ...]    ; 0x379c
10b7f2: movs r3, #1
10b7f6: strb r3, [r4, r2]     ; this+0x379c = 1
10b7f8: subs r2, #0x71
10b7fa: subs r2, #0xff
10b7fc: strb r3, [r4, r2]     ; this+0x362c = 1
```

That means the forced branch did not “open stage select.” It explicitly asserted the same two worldmap-local gate bytes that the touch handlers consume. Because of that, `native-worldmap-updatemenu-auto-local-branch` was removed from the default offline-hook build path.

`OnPointerRelease` is also now clearly identified as a switch over `([this+4] - 5)`, not a generic tap sink. In the relevant cases it:

- records touch coordinates into `this+0xf8/0xfa`
- clears `this+0xfc/0xfd`
- sets `this+0xfe = 1`
- dispatches through a jump table based on the current worldmap substate
- in one concrete branch, writes `this+0x36f8 = 7`

So the correct next target is not another forced transition. The correct next target is the real writer/clearer path for `0x36f8`, `0x362c`, and `0x379c` under the active worldmap substate.

## Current Conclusion

The next safe fix is not another branch redirection.

The next safe fix is to identify who sets and clears:

- `global + 0x1068`
- `this + 0x379c`
- `this + 0x362c`

and then restore the expected memory state at the right lifecycle point.

## Lifecycle Update

Additional access tracing now narrows the problem further:

- `global + 0x1068`
  - still appears as a read-side gate in worldmap and script/game paths
  - no direct writer has been confirmed yet
- `this + 0x379c`
  - confirmed writers:
    - `CreateMainLoop` clears it during setup
    - `DrawUpdateFadeIN` clears it after fade completion
    - `DrawNetMenu` writes it during menu visibility/update flow
    - `UpdateWorldMapMenu` writes it when menu/UI control paths return transition state
- `this + 0x362c`
  - confirmed to be written by a large set of worldmap popup, shop, net, and menu flows
- `this + 0x36f8`
  - currently appears as a worldmap-local menu/state slot touched by `OnPointerRelease` and `UpdateWorldMapMenu`

The current leading hypothesis is that the previous default patch set over-cut worldmap network handlers:

- `CPdStateWorldmap::OnNetError`
- `CPdStateWorldmap::OnNetReceive`

Those callbacks were patched to `bx lr` no-op form to suppress dead-service fallout. Static analysis now suggests that this likely removed worldmap-local cleanup together with network UI, leaving `0x379c`, `0x362c`, or `0x36f8` latched when the map should have become interactive.

Because of that, the default offline-hook build no longer patches worldmap `OnNetError`/`OnNetReceive`. The current direction is:

1. keep upstream network bootstrap bypasses
2. preserve worldmap-local callback cleanup
3. avoid forced `UpdateWorldMapMenu` transitions that set `0x379c/0x362c`
4. only patch the specific network popup/launcher gates that are still external blockers

## Additional April 4 Static Closure

The worldframe hit-result byte is now closed more tightly.

Automated scan:

- [trace_aw2_worldmap_hit_result.py](/C:/vs/other/arelwars/tools/arel_wars2/trace_aw2_worldmap_hit_result.py)
- [aw2_worldmap_hit_result_accesses.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_hit_result_accesses.json)

Confirmed minimal access set:

- `CPdStateWorldmap::TouchInputWorldFrame(int, int)`
  - writes `r0` into `[this + 0x200]` after `CCommonUI::TouchInputWorldFrame(...)`
- `CPdStateWorldmap::DoTouchMoveWorldArea(int, int)`
  - reads `[this + 0x200]`
  - if nonzero, it clears the byte and returns before the generic world-area rectangle scan runs

This means `0x200` is not itself the stage-select transition field. It is only a short-lived press/result latch between the press handler and the mixed release helper.

`CCommonUI::TouchInputWorldFrame(int, int)` was also re-read directly. It does not create stage select or game start. It only calls `CPdSharing::ClickButtonIcon(...)` against up to four icon pointers and returns the OR-ed hit result.

That narrows the live hypothesis in a different direction than before:

- `0x200` is an overlay/button-layer hit latch, not a base-area index
- a nonzero `0x200` means the release helper consumed an icon/button path and never entered the generic area scan
- base world-area selection only begins when `0x200 == 0`

## DrawLoading / State Table Closure

State-table report:

- [trace_aw2_worldmap_state_tables.py](/C:/vs/other/arelwars/tools/arel_wars2/trace_aw2_worldmap_state_tables.py)
- [aw2_worldmap_state_tables.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_state_tables.json)

Confir