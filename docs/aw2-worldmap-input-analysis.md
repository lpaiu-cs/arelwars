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

## Current Conclusion

The next safe fix is not another branch redirection.

The next safe fix is to identify who sets and clears:

- `global + 0x1068`
- `this + 0x379c`
- `this + 0x362c`

and then restore the expected memory state at the right lifecycle point.

## Tooling

Automated literal/function scan:

- [analyze_worldmap_input_flags.py](/C:/vs/other/arelwars/tools/arel_wars2/analyze_worldmap_input_flags.py)
- [aw2_worldmap_input_flags.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_worldmap_input_flags.json)
