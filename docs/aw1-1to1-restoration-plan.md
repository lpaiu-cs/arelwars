# AW1 1:1 Restoration Plan

This file is the working checkpoint for the long-running Arel Wars 1 restoration effort.
It exists to keep the project on the same execution path even after long gaps or context resets.

## Goal

Ship a modern Android and iOS build that is behaviorally equivalent to the original `arel_wars_1.apk`.

Behavioral equivalence means:

- story progression matches the original
- battle outcomes match the original under the same inputs
- sprite timing, palette/state changes, and effects are visually close enough to be indistinguishable in normal play
- save/load, results, failure states, and menu flow behave the same way

It does not mean rebuilding the original binary. The original source is gone. This is a clean reimplementation backed by recovered assets and reverse-engineered data.

## Current Baseline

- APK extraction, cataloging, and modern runtime packaging are already in place.
- `ZT1` dialogue extraction is operational, including structured speech prefix commands.
- `PZX` first-stream decoding, frame/tail metadata splitting, timing inference, and `MPL` bank heuristics are operational enough for preview playback.
- `179.pzx` now has a usable packed-pixel preview heuristic.
- `PTC` is structurally parsed as stable parameter blocks.
- Capacitor Android builds and runs the current recovery runtime.

References:

- [arel_wars1-recovery.md](/Users/lpaiu/vs/others/arelwars/docs/arel_wars1-recovery.md)
- [arel_wars_shared-reverse-engineering-notes.md](/Users/lpaiu/vs/others/arelwars/docs/arel_wars_shared-reverse-engineering-notes.md)
- [aw1-script-opcode-notes.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-script-opcode-notes.md)
- [aw1-gxl-table-notes.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-gxl-table-notes.md)
- [aw1-stage-progression-notes.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-stage-progression-notes.md)

## Hard Gaps To Close

### 1. Script Semantics

- All `cmd-XX` speech-prefix opcodes need concrete engine meanings.
- Non-dialogue progression commands must map to actual gameplay actions:
  - scene changes
  - stage start/end
  - unit or wave triggers
  - map or UI state changes
  - reward/result flow

### 2. Battle Data

- Stage, unit, spawn, AI, and rules data still need canonical schemas.
- The remake runtime does not yet run a deterministic battle simulation.

### 3. Rendering And Effects

- `179.pzx` still uses a heuristic shade model.
- `PTC` needs to become real effect playback, not just parsed metadata.
- `PZX` tail metadata and `MPL` bank switching need to be connected to runtime sprite states, not just preview probes.

### 4. Full Game Flow

- Current runtime is a recovery viewer, not a complete game loop.
- Missing pieces include:
  - title/menu flow
  - stage selection or campaign progression
  - in-battle HUD and controls
  - result/retry flow
  - save/load behavior
  - audio event mapping

## Execution Order

### Phase 1. Freeze Ground Truth

- Capture reference footage and notes from the original APK running in a legacy environment.
- Build a stage-by-stage verification checklist.
- Record story, battle, result, and menu behaviors that must be matched.

### Phase 2. Recover Script Meaning

- Expand `ZT1` analysis around unknown prefix opcodes.
- Correlate opcode patterns with:
  - speaker tags
  - stage scripts
  - dialogue boundaries
  - portrait/expression changes
  - observed gameplay transitions
- Rename `cmd-XX` into stable semantic commands only when evidence is strong.

### Phase 3. Recover Canonical Gameplay Data

- Identify the files that hold:
  - stage definitions
  - unit stats
  - spawn waves
  - AI or behavior rules
  - upgrade or reward tables
- Export them into typed JSON that the new runtime can consume directly.
- Current strongest source family is `GXL` under `assets/data_eng/*.zt1` and `assets/data_kor/*.zt1`.
  - `54/54` decoded AW1 `GXL` tables now satisfy a fixed-size row layout.
  - current working header model:
    - `magic = GXL\x01`
    - `rowSize(u16)`
    - `headerExtraSize(u16)`
    - `rowCount(u16)`
    - `headerSize = 10 + headerExtraSize`
    - `payloadSize = rowSize * rowCount`
  - first extraction targets:
    - `XlsLevelDesign`
    - `XlsMap`
    - `XlsAi`
    - `XlsHero`
    - `XlsProjectile`
    - `XlsParticle`
  - current parsed-table outputs now exist for:
    - `XlsAi.eng`
    - `XlsWorldmap.eng`
    - `XlsMap.eng`
    - `XlsLevelDesign.eng`
    - `XlsHero.eng`
    - `XlsHeroSkill.eng`
    - `XlsItem.eng`
    - `XlsHero_Ai.eng`
    - `XlsSkill_Ai.eng`
    - `XlsProjectile.eng`
    - `XlsEffect.eng`
    - `XlsBaseAttack.eng`
    - `XlsParticle.eng`
    - `XlsHeroActiveSkill.eng`
    - `XlsHeroBuffSkill.eng`
    - `XlsHeroPassiveSkill.eng`
    - `XlsBalance.eng`
    - `XlsCorrespondence.eng`
  - current cross-correlation outputs now exist for:
    - [AW1.stage_progression.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_progression.json)
    - [AW1.map_binding_candidates.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.map_binding_candidates.json)
    - [AW1.inline_map_pointer_scan.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.inline_map_pointer_scan.json)
    - [AW1.stage_map_proofs.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_map_proofs.json)
    - [AW1.battle_catalog.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_catalog.json)
    - [AW1.effect_runtime_links.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json)
    - [AW1.hero_skill_links.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_skill_links.json)
    - [AW1.hero_runtime_families.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_runtime_families.json)
    - [AW1.hero_runtime_archetypes.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_runtime_archetypes.json)
    - [AW1.opcode_action_map.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.opcode_action_map.json)
    - [AW1.runtime_blueprint.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json)
  - current strongest runtime-field candidates in `XlsAi` are:
    - `tierCandidate = numericBlock[13]`
    - `variantCandidate = numericBlock[15]`
    - `regionCandidate = numericBlock[16]`
    - `storyFlagCandidate = numericBlock[18]`
  - current strongest `assets/map/*.zt1` header model is:
    - `version`
    - `layerCount`
    - `width`
    - `height`
    - reserved fields
    - `variantOrGroup`
  - current strongest effect/runtime linkage findings are:
    - `XlsParticle` is now a high-confidence `PTC bridge table`
    - `12/12` primary ids and `10/10` nonzero secondary ids resolve directly to `ptc/NNN.ptc`
    - `XlsHeroActiveSkill.tailPairBE` produces exact projectile/effect hits in `5/25` rows
    - `XlsHeroSkill.slotOrPowerCandidate` is now a high-confidence direct slot index into `XlsHeroPassiveSkill` for slots `0..23`
    - the same slot index reaches `24/25` rows in `XlsHeroActiveSkill`, leaving only active row `24` orphaned for now
    - `XlsHeroBuffSkill.tailLinkCandidate` also behaves like a slot bridge when non-`255`
    - `AW1.hero_runtime_families.json` now captures the strongest runtime clusters:
      - `Dispatch` as a three-slot passive-active-buff ladder on `20/21/22`
      - `Defend Tower` as a hero-specific tower-defense family on `6/13/23`
      - shared-slot hybrids on `11`, `14`, and `15`
      - `29/30/31` as special command slots outside the passive/active row range
    - `AW1.hero_runtime_archetypes.json` now turns those clusters into engine-facing archetype candidates:
      - `Dispatch` -> `respawn-redeploy-cooldown-ladder`
      - `Tower Defense` -> `tower-defense-stance-ladder`
      - `Natural Healing` / `Recall` -> slot-11 shared channel
      - `Mana Wall` / `Armageddon` -> slot-15 shared channel
      - `Smoke` regular skill and `Smoke (Special)` are now separated instead of being conflated by name
    - `AW1.opcode_action_map.json` now separates mnemonic-wide opcode labels from variant-local action hints
    - `AW1.tutorial_opcode_chains.json` now records exact raw-prefix tutorial chains for the battle HUD and menu-training families, which is important where the current prefix parser still under-reads selector bytes
    - the recovery runtime now resolves those tutorial chains per dialogue event instead of only exposing them as family-level metadata
    - the Phaser recovery scene now draws a tutorial-driven HUD ghost layer, so tower HP, mana, cards, menus, and quest panels visibly react to the active dialogue cue
    - `AW1.inline_map_pointer_scan.json` now shows that `XlsAi.numericBlock byte[15]` and `byte[18]` reproduce the current pair-base and pair-branch selection with exact `111/111` coverage
    - `AW1.stage_map_proofs.json` now gives each stage a scored map-binding proof candidate and upgrades the proof type to `inline-ai-pointer-derived`
    - `AW1.runtime_blueprint.json` now joins stage blueprints, opcode heuristics, scored map proofs, archetypes, and render cues into one runtime-facing manifest

### Phase 4. Build Deterministic Runtime Systems

- Story/scene interpreter
- battle simulation
- unit and projectile systems
- wave scheduler
- win/lose evaluation
- save/load state

### Phase 5. Replace Preview Rendering With Game Rendering

- Convert recovered timeline metadata into runtime animation/state machines.
- Connect `MPL` bank switching and `PTC` parameter blocks to visible sprite/effect playback.
- Resolve `179.pzx` from preview heuristic toward final in-engine shading behavior.

### Phase 6. Validation And Packaging

- Compare rebuilt stages against legacy reference runs.
- Tune timing/state differences.
- produce stable Android release builds
- produce iOS builds once full Xcode is available

## Immediate Work Queue

1. Expand `ZT1` opcode analysis so every unknown opcode has:
   - count
   - arg-pattern histogram
   - co-occurring commands
   - representative script samples
2. Keep promoting `cmd-XX` groups from mnemonic-wide hints to proven engine actions as binary grammar evidence improves.
3. Trace candidate battle/state source files and define a first canonical schema.
4. Replace the current scored `stage_map_proofs` layer with the first hard pointer that links:
   - `script family / XlsAi row`
   - `tierCandidate / variantCandidate / regionCandidate`
   - concrete `assets/map/*.zt1` payload selection
5. Continue promoting compact battle tables into runtime-ready schemas:
   - hero AI
   - item/active-skill AI
   - projectile definitions
   - effect definitions
   - hero active/passive/buff skill definitions
6. Promote slot-linked hero runtime families into engine-facing archetypes:
   - `Dispatch`
   - `Tower Defense`
   - `Natural Healing / Recall`
   - `HP Up / Return to Nature`
   - `Mana Wall / Armageddon`
   - `Mana Gain`
7. Turn those archetypes into actual runtime systems in the remake engine:
   - shared active channels
   - buff trigger ladders
   - hero-variant tower-defense stances
   - special command payload handling for slots `29/30/31`
8. Keep replacing heuristic stage/bootstrap glue with proven pointers:
   - `script family -> AI row -> concrete map bin`
   - `cmd-XX -> engine action`
   - `PTC/MPL/179 -> final render implementation`

## First Opcode Findings

These are still provisional and should not be promoted to final command names yet.

### Likely Presentation Helpers

- `cmd-05`
  - usually follows a portrait change and is usually followed by `cmd-08`
  - strongest current interpretation: a dialogue presentation helper, likely active pose, mouth, or focus state rather than gameplay logic
- `cmd-08`
  - usually terminates the same short prefix sequences that include `cmd-05`
  - strongest current interpretation: end-of-presentation or secondary presentation toggle
- `cmd-0a` and `cmd-0b`
  - often appear together with argument `0x10`
  - cluster around impact, surprise, pain, or emphasis lines
  - strongest current interpretation: paired emphasis or shake-style presentation commands

### Likely Tutorial Or UI Focus Commands

- `cmd-02`, `cmd-06`, `cmd-0a`, `cmd-0c`
  - tutorial scripts under `0004`, `0014`, and nearby files use these around explicit UI instructions such as tower HP, path arrows, skill menu, and item menu
  - strongest current interpretation: UI focus, highlight, or guided-tutorial targeting commands
- The recurring `0x40` argument in those tutorial sequences looks more like a UI-region or mode selector than a character-expression value.

### Likely Scene Or Encounter Presets

- `cmd-10`, `cmd-18`, `cmd-0d`, `cmd-1e`, `cmd-25`, `cmd-43`
  - often appear at the first spoken line of a scene or encounter
  - strongest current interpretation: scene-entry preset, camera/layout preset, or encounter-state bootstrap commands

### Where To Look Next

- tutorial scripts:
  - `assets/script_eng/0004.zt1.events.json`
  - `assets/script_eng/0014.zt1.events.json`
- scene-opening presets:
  - `assets/script_eng/0001.zt1.events.json`
  - `assets/script_eng/0023.zt1.events.json`
  - `assets/script_eng/0300.zt1.events.json`
- emphasis / impact clusters:
  - `assets/script_eng/0053.zt1.events.json`
  - `assets/script_eng/0092.zt1.events.json`

## Done When

- The runtime is no longer a recovery viewer.
- A complete stage can be played from script start to result screen.
- The same stage in the original APK and the remake produces matching event order and battle outcome.
- Release APK packaging is routine rather than special-case recovery packaging.
