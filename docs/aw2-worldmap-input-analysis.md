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

Confirmed:

- `DrawLoading` reads the pending loading action from `[this + 0x34]`
- `DrawLoading` case `4` creates stage select
- `DrawLoading` case `5` creates stage info
- `DrawLoading` case `17` creates game start

Direct caller scan shows:

- `CreateStageSelect`, `CreateStageInfo`, and `CreateGameStart` are directly called from `DrawLoading`
- they are not directly called from `TouchInputWorldMapMenu` or `OnPointerRelease`

Pointer dispatch is also now fixed numerically:

- `OnPointerPress` uses `([this+4] - 5)` jump dispatch
  - state `5` goes directly to `TouchInputWorldFrame`
- `OnPointerRelease` uses the same state bias
  - state `5` goes to the mixed overlay helper `DoTouchMoveWorldArea`

So the current main-state structure is:

1. press on state `5` calls `TouchInputWorldFrame`
2. `TouchInputWorldFrame` only latches the hit result and button state
3. release on state `5` mainly resolves overlay/menu candidates
4. the real stage transition must be scheduled later through update/loading state, not by direct release-time scene creation

## Current Bottleneck After Town SHOP Progress

The user observation that `Town SHOP` responds while `DESERT PLAIN` / `PVP` do not is now consistent with the static model:

- overlay/town-menu path inside `DoTouchMoveWorldArea` is alive
- base world areas are a different release-time rectangle path that only runs after the overlay/button latch has already come back zero
- the remaining blocker is therefore inside generic area selection (`0x100`, `0x36f8`, `state 2`) rather than inside `ClickButtonIcon(...)` follow-up scheduling

That makes the next safe target narrower than before:

- stop touching `CreateStageSelect` directly
- stop treating `DoTouchMoveWorldArea` as the real stage owner
- inspect the generic area rectangle / same-area re-tap / `UpdateWorldMapMenu` consumer path

## Additional April 4 Selection-Flow Closure

The base worldframe path is now closed more tightly than before.

Automated trace:

- [trace_aw2_worldmap_selection_flow.py](/C:/vs/other/arelwars/tools/arel_wars2/trace_aw2_worldmap_selection_flow.py)
- [aw2_worldmap_selection_flow.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_selection_flow.json)

Confirmed structure:

1. a new area hit inside `DoTouchMoveWorldArea(...)` does **not** immediately request stage select
2. the new-area path stores the candidate index into `this + 0x100`
3. it then calls `InitWorldmapSltAreaAni(...)`
4. only a **same-area re-tap** goes through `IsCheckAreaEnter(...)`
5. if enterable:
   - `this + 0x379c = 1`
   - `this + 0x36f8 = this + 0x100`
6. if not enterable:
   - `this + 0x362c = 1`
   - a worldmap popup is created instead

One more correction matters here:

- `CPdStateWorldmap::TouchInputWorldFrame(...)` is not the generic area selector
- its `[this+0x200]` result comes from `CCommonUI::TouchInputWorldFrame(...)`, which only ORs button/icon hits
- `DoTouchMoveWorldArea(...)` enters the generic area rectangle loop only when that overlay result is zero

`UpdateWorldMapMenu(...)` is the first confirmed consumer of that armed area state:

- it reads `this + 0x379c`
- it reads `this + 0x36f8`
- if `0x36f8` is `0..4`, it mirrors the area index into another worldmap field, sets `[this+8] = 2`, snapshots `[this+4] -> [this+0xc]`, and clears `0x36f8 = -1`
- if `0x36f8 == 5`, it schedules state `0x19` instead

That means the current bottleneck is even narrower:

- overlay/menu buttons such as `Town SHOP` can still work without proving base area entry
- `DESERT PLAIN` / `PVP` not reacting means either:
  - the base-area hit-test never selects an area, or
  - the same-area re-tap never arms `0x379c/0x36f8`, or
  - `UpdateWorldMapMenu(...)` never consumes the armed pending-area state under the active runtime conditions

This also justifies tightening the default build path:

- blind guard removals on `OnPointerPress`, `TouchInputWorldMapMenu`, and `TouchInputWorldFrame` are no longer treated as safe default fixes
- the default build keeps only the lower-risk worldmap reopening patches such as tap-slop widening and consumer-slot alignment
- direct `CreateStageSelect` forcing remains out of bounds

## Additional April 4 Area / State Closure

Additional report:

- [trace_aw2_worldmap_area_state_flow.py](/C:/vs/other/arelwars/tools/arel_wars2/trace_aw2_worldmap_area_state_flow.py)
- [aw2_worldmap_area_state_flow.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_area_state_flow.json)

Three new facts matter:

1. `IsCheckAreaEnter(...)` is now simple enough to reason about.
   - `area == 5` returns true immediately
   - otherwise it compares a global progress field against `areaIndex * 15`
   - for normal non-negative progress values, the effective condition is `globalProgress24 >= areaIndex * 15`
2. `UpdateWorldMapMenu(...)` really does split the worldmap areas into two families.
   - pending area `0..4`:
     - mirror area into `this + 0x361c`
     - set pending state `[this+8] = 2`
     - snapshot `[this+4] -> [this+0xc]`
     - clear `this + 0x36f8 = -1`
   - pending area `5`:
     - set pending state `[this+8] = 0x19`
     - snapshot `[this+4] -> [this+0xc]`
     - clear `this + 0x36f8 = -1`
3. `MakeBufferStageSelect(...)` is the strongest current consumer of the generic path.
   - it reads `this + 0x361c`
   - it explicitly special-cases `[this+4] == 2`
   - therefore state `2` is the confirmed generic world-area -> stage-select preparation state

That gives a tighter interpretation of the current live behavior:

- `Town SHOP` responding while base world objects do not is consistent with the special `pendingArea == 5` path still working
- `DESERT PLAIN` / `PVP` not reacting means the generic `0..4` area path is still failing before or during the `state 2` transition
- the next safe debugging targets are:
  - whether `0x100` is actually updated on first hit
  - whether a same-area re-tap is arming `0x379c / 0x36f8`
  - whether the `state 2` transition is being consumed after `UpdateWorldMapMenu(...)`

## Additional April 4 Layer Split / Seed Closure

`Select_WorldmapMenu(...)` was re-read directly after the Town SHOP-only live result.

Two more facts are now fixed:

1. `Select_WorldmapMenu(...)` seeds `this + 0x100` during worldmap menu entry.
   - it resolves an initial area index
   - if that index is `0..4`, it stores it into `this + 0x100`
   - it then calls `InitWorldmapSltAreaAni(...)`
2. `Town SHOP` and generic world areas are not on the same press/release layer.
   - `Town SHOP`-style buttons can respond through the overlay path
   - generic areas `0..4` only progress through the rectangle loop and then the same-area re-tap latch path

So the current live interpretation is now:

- the worldmap already enters with some seeded selected area state
- overlay buttons can still behave independently of that base-area state
- `DESERT PLAIN` / `PVP` staying dead means the generic `0..4` area rectangle path is still the real blocker

## Additional April 4 Pre-Area Gate Closure

Another pre-area helper is now closed:

- `DoTouchMoveWorldArea(...)` calls `TouchGamevilLiveBtns(x, y)` before it enters the generic world-area rectangle scan
- if that helper returns nonzero, the base-area path is skipped entirely

Static disassembly shows two immediate early-return conditions inside `TouchGamevilLiveBtns(...)`:

1. `global + 0x1068 != 0`
2. `this + 0x36f0 != -1`

That second field is now a concrete candidate. `0x36f0` looks like a worldmap-local active GamevilLive / overlay button slot:

- `DrawGamevilLiveBtns(...)` writes `-1` in its reset path
- `OnNetError(...)` writes `1` in one network-error branch
- `SelectNetFriendList(...)` also writes and clears the nearby block

This still does **not** prove that `0x36f0` is the main live blocker, because `Town SHOP` responds and therefore the worldmap is not universally swallowed before any UI handling. But it is now a narrowed stale-state candidate:

- if `0x36f0` is left at `1` by a dead-service/network branch
- and the reset path no longer runs normally under offline conditions
- then `TouchGamevilLiveBtns(...)` can keep returning `1`
- and the generic `DESERT PLAIN` / `PVP` area scan never even starts

So the current narrowed possibilities are:

- generic area selection never latches (`0x100`)
- same-area enter never arms (`0x379c / 0x36f8`)
- pending `state 2` is never consumed
- or `TouchGamevilLiveBtns(...)` is still swallowing some releases before the base-area path

## Tooling

Automated literal/function scan:

- [analyze_worldmap_input_flags.py](/C:/vs/other/arelwars/tools/arel_wars2/analyze_worldmap_input_flags.py)
- [aw2_worldmap_input_flags.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_input_flags.json)
- [trace_aw2_worldmap_flag_accesses.py](/C:/vs/other/arelwars/tools/arel_wars2/trace_aw2_worldmap_flag_accesses.py)
- [aw2_worldmap_flag_accesses.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_flag_accesses.json)
- [trace_aw2_worldmap_selection_flow.py](/C:/vs/other/arelwars/tools/arel_wars2/trace_aw2_worldmap_selection_flow.py)
- [aw2_worldmap_selection_flow.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_selection_flow.json)
- [trace_aw2_worldmap_area_state_flow.py](/C:/vs/other/arelwars/tools/arel_wars2/trace_aw2_worldmap_area_state_flow.py)
- [aw2_worldmap_area_state_flow.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_area_state_flow.json)
