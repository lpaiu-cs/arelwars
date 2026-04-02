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
- `PZX` root typing is now anchored to native-confirmed `PZD/PZF/PZA` offsets, and preview exports carry that typed subresource graph per stem.
- `PZX` first-stream decoding, `PZF` frame-pool parsing, `PZA` clip parsing, and heuristic tail-group analysis are operational enough for preview playback.
- `179.pzx` now has a stronger special-case structural mapping, but it is still treated as stem-specific rather than a generic palette rule.
- `PTC` is structurally parsed as stable parameter blocks.
- battle rendering now drives sprite-state overlays, hit flash, burst pulses, particle boosts, and camera shake from deterministic combat events rather than static preview pulses.
- Capacitor Android builds and runs the current recovery runtime.

References:

- [arel_wars1-recovery.md](/Users/lpaiu/vs/others/arelwars/docs/arel_wars1-recovery.md)
- [arel_wars_shared-reverse-engineering-notes.md](/Users/lpaiu/vs/others/arelwars/docs/arel_wars_shared-reverse-engineering-notes.md)
- [aw1-native-branch-alignment.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-native-branch-alignment.md)
- [aw1-script-opcode-notes.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-script-opcode-notes.md)
- [aw1-gxl-table-notes.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-gxl-table-notes.md)
- [aw1-stage-progression-notes.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-stage-progression-notes.md)
- [aw1-phase1-10-audit.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-phase1-10-audit.md)

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
- The remake runtime now runs a deterministic entity-step combat core with unit, projectile, effect, mana, population, cooldown, and AI ticks driven by recovered battle-model templates, but it is still not a full 1:1 battle engine.

### 3. Rendering And Effects

- `179.pzx` now uses a stronger special-case structural mapping, but it still needs original-reference validation before it can be treated as fully native-confirmed.
- `PTC` semantics are now consumed by the runtime renderer, but emitter behavior is still reconstructed rather than confirmed from original engine code.
- `PZX` tail-group candidates and grouped overlay cadence now drive runtime sprite states, overlays, and flashes, but they remain runtime-consistent heuristics unless tied to a matching native consumer.

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
    - [AW1.stage_bindings.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json)
    - [AW1.battle_catalog.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_catalog.json)
    - [AW1.effect_runtime_links.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json)
    - [AW1.hero_skill_links.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_skill_links.json)
    - [AW1.hero_runtime_families.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_runtime_families.json)
    - [AW1.hero_runtime_archetypes.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_runtime_archetypes.json)
    - [AW1.engine_schema.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.engine_schema.json)
    - [AW1.battle_model.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_model.json)
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
    - that same cue layer now drives a lightweight gameplay-state machine with panel, hero, objective, and enabled-input summaries
    - the Phaser recovery scene now routes keyboard input through that state machine, so panel open/close and hero sortie/return transitions can be exercised instead of only visualized
    - accepted actions now leave persistent preview state behind: lane selection, queued units, tower upgrade tiers, skill/item cooldowns, quest reward claims, and pause/resume all feed the ghost HUD
    - the recovery system now owns a deterministic two-lane battle preview, so dispatch, queued units, and hero sortie affect lane frontline, momentum, and unit counts instead of only HUD chrome
    - that lane preview is now seeded from each storyboard's stage blueprint and featured archetypes, so tempo, favored lane, and hero impact vary per reconstructed stage
    - archetype families now change the lane sim differently: Dispatch accelerates allied commits, Tower Defense hardens favored lanes, Recall pulls pressure back toward safety, Armageddon bursts enemy units, and mana-oriented channels soften skill costs
    - dialogue-level tutorial and opcode cues now trigger one-shot scripted battle beats as the scene advances, which lets recovered lines automatically prime lanes, queue units, deploy or recall the hero, fire skills or items, and advance tower upgrades while keeping manual input state separate
    - the lane simulation now tracks an explicit battle objective phase plus allied/enemy wave countdowns, so storyboard playback exposes opening, lane-control, hero-pressure, tower-management, skill-burst, quest-resolution, and siege transitions instead of only raw pressure numbers
    - stage blueprints now also emit per-wave allied/enemy spawn directives, so each reconstructed storyboard carries its own lane-focused reinforcement pattern instead of only one global cadence rule
    - dialogue-level tutorial and opcode transitions can now immediately fire the current stage-specific wave directive, so major scene beats advance or materialize reinforcements instead of waiting only on countdown cadence
    - the recovery battle loop now resolves victory and defeat, exposes a short result hold with auto-advance, and flips successful stages into quest/reward review instead of leaving every storyboard permanently in an active battle state
    - when a storyboard reaches its last recovered dialogue line, playback now holds that line on screen until the battle loop resolves instead of jumping away before the result is known
    - victory now unlocks the next campaign node while defeat retries the current node, so storyboard playback has a minimal worldmap-like progression layer instead of one flat linear rotation
    - the recovery runtime now exposes a real campaign node strip with unlocked, cleared, active, selected, and recommended states, and paused/result phases allow ArrowLeft/ArrowRight selection plus Enter-based stage launch
    - the campaign loop is now explicitly split into `battle -> result hold -> worldmap selection -> deploy briefing -> battle`, with auto-transition timers and selected-node brief text exposed to both the Phaser scene and the DOM storyboard
    - deploy briefing now carries node-specific objective phase, favored lane, tactical bias, first-wave allied/enemy forecast, and recommended archetype labels, so route selection has pre-battle intel instead of only a title swap
    - deploy briefing now also exposes loadout presets, and the chosen preset changes battle start conditions such as queue depth, mana stock, tower upgrade tiers, opening panel, and hero starting lane when the next node launches
    - deploy loadouts now model hero roster role, skill preset, and tower opening policy, and those choices continue to affect skill casts, tower upgrade defaults, mana tempo, and hero deploy/return behavior after the battle begins
    - active deploy loadouts now also retune allied/enemy wave directives and scripted scene beats, so roster/skill/policy choices change lane targeting, burst size, rally timing, and counter-pressure during the battle instead of only changing initial conditions
    - hero roster roles and skill presets now modulate battle channels and can auto-fire roster-specific scripted actions during dialogue beats, so deploy selection affects not just wave labels but which channels spike and which helper actions get injected at tutorial/opcode transitions
    - hero roster members now also read stage-script bias from the current storyboard title/hint/objective, so the same squad behaves differently on siege, hold, dispatch, mana, and reward-oriented stages instead of using one global member profile
    - campaign route bias now also steers the recommended worldmap node and default deploy loadout, so paused/result selection and briefing defaults follow branch semantics instead of only the next sequential unlock
    - campaign flow now keeps a route commitment and future route goal, so branch-following victories continue to bias recommendation, default loadout selection, and locked-node targeting across multiple stage clears instead of only one handoff
    - route commitment now also reshapes stage profile, objective seed, wave directives, and deploy start conditions, so the same node opens with different pressure, cadence, loadout posture, and lane emphasis depending on which branch flow led into it
    - route commitment now also modulates dialogue-triggered wave beats and victory/defeat thresholds, so committed branches resolve scripted pressure spikes and battle outcomes differently instead of only changing pre-battle setup
    - committed branch flows can now emit roster-specific scripted action chains such as deploy+burst, queue+sortie, or fortify+item on the same cue, so repeated tutorial/opcode beats no longer always collapse to one generic helper action
    - roster action chains now leave transient member boosts that directly nudge lane entities, tower/mana state, and channel intensity for a few beats, so scripted chains read as visible combat swings instead of only hidden state updates
    - active chain summaries are now exposed to the battle snapshot and UI, with focused-lane highlighting and chain member/intensity readouts, so temporary route/roster surges are directly visible in both DOM and Phaser overlays
    - battle state is now derived from deterministic unit and projectile collections instead of direct aggregate pressure writes, so dispatches, waves, hero deploys, skills, items, and scripted chains all enter the same `spawn -> move -> attack -> hit -> die -> derive lane state` loop
    - the Phaser lane preview now renders those runtime entities and projectiles directly, which means the on-screen combat line is finally reading from the same deterministic core that resolves tower damage, frontline shifts, and wave pressure
    - `AW1.battle_model.json` now exports engine-facing unit, projectile, effect, skill, item, hero, and resource templates from recovered tables, and the runtime consumes those templates for actual mana spending, population caps, cooldown scheduling, spawn gating, projectile/effect playback, and allied/enemy AI ticks instead of treating those systems as HUD-only hints
    - `AW1.engine_schema.json` now fixes `XlsUnit`, `XlsHero`, `XlsHero_Ai`, `XlsSkill_Ai`, `XlsProjectile`, `XlsEffect`, `XlsParticle`, and `XlsBalance` into one canonical engine-input export with raw slots plus stable `engineHints`, and `AW1.battle_model.json` now derives the covered sections from that schema instead of re-reading those tables indirectly
    - phase-2 hardening also moved runtime tower HP changes behind shared `damage/repair` helpers and made direct entity spawns respect battle population caps unless a scene seed explicitly bypasses them, which closes the main remaining preview-era escape hatches in the combat core
    - result resolution no longer keys off lane-pressure momentum thresholds; it now reads actual wave-dispatch exhaustion, on-field entity/projectile clearance, secured lane counts, queue/mana exhaustion, and tower collapse state before declaring victory or defeat
    - route/branch selection is now elevated into a shared route-bias layer, so briefing text, tactical bias, favored lane, wave plan cadence, deploy summaries, and member-specific behavior all react to `primary` vs `secondary` route semantics instead of treating branch labels as cosmetic
    - `AW1.inline_map_pointer_scan.json` now shows that `XlsAi.numericBlock byte[15]` and `byte[18]` reproduce the current pair-base and pair-branch selection with exact `111/111` coverage
    - `AW1.stage_bindings.json` now fixes every current script-backed stage as `hard-script-ai-inline-map`, with exact `script family == XlsAi row index` binding and exact `preferredMapIndex = pairBase + pairBranch`
    - `AW1.runtime_blueprint.json` now joins stage blueprints, opcode heuristics, hard stage bindings, archetypes, and render cues into one runtime-facing manifest
    - phase-6 opcode export now covers all `64` currently observed non-dialogue `cmd-XX` families with `unresolvedOpcodeCount = 0`, and every exported mnemonic/variant now carries stable `commandId`, `commandType`, and `target` fields in `AW1.opcode_action_map.json`
    - the prefix sanitizer now strips ASCII spill without dropping stable tutorial raw chains, so `AW1.tutorial_opcode_chains.json` is back to `15/15` matched chains after the opcode export widened to full-family coverage
    - the runtime scene interpreter now resolves `activeSceneCommands[]` per dialogue event and consumes scene-layout, focus, presentation, emphasis, and transition commands directly instead of only picking one representative opcode string
    - dialogue playback is now backed by precompiled `sceneScriptSteps[]` per storyboard, so objective changes, panel transitions, wave triggers, dispatch commits, mana restores, scripted actions, and scene notes are executed from an explicit step directive list instead of a large cue-switch inside `applyDialogueBeat()`
    - `AW1.render_pack.json` now packages 21 recovered sprite stems, 7 MPL bank probe sheets, the corrected `179` packed-pixel composite, and the full linked PTC emitter set into one runtime-facing render manifest, and the Phaser scene now renders battle entities/projectiles/effects from those recovered assets instead of primitive circles and rectangles
    - `AW1.render_semantics.json` now fixes three remaining render ambiguities into canonical exports: `179` uses `value == 0` transparency plus `normalized = value - 1` over a 47-color four-band model with a `189..199` additive highlight tail, MPL bank switching is exported from exact anchor/tail item flags per frame, and every linked `XlsParticle` row now exposes named PTC emitter semantics with timing/emission/radius/delta fields

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
4. Use the hard `AW1.stage_bindings.json` layer as the campaign/runtime source of truth and keep tightening the original semantic names around that exact binding path.
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
9. Phase12 baseline is now in place:
   - local save/load and resume slots
   - retry-stage entry
   - runtime settings for audio, autosave, auto-advance, resume-on-launch, reduced effects
   - synthesized audio cues and ambient layer switching
   - constructor-time session restore plus before-unload resume persistence
10. Phase13 baseline is now in place:
   - the runtime no longer builds storyboards from a 6-stage featured sample
   - web `catalog.json` now carries full `zt1Entries`, and all required English stage scripts export `webEventsPath`
   - the campaign flow is assembled from all `111` hard-bound stage blueprints in `AW1.runtime_blueprint.json`
   - current coverage check is `111` stage blueprints, `312` required script files, `312` available English script event exports, `0` missing stage script files
11. Phase14 baseline is now in place:
   - `AW1.verification_spec.json` now defines exact and tolerant comparison gates for all `111` stages
   - the runtime exports machine-readable verification traces with scene phases, objective phases, wave counts, dialogue anchors, and result/unlock checkpoints
   - comparison tooling now exists for `spec + remake trace + legacy trace` workflows instead of relying on ad-hoc screenshot inspection
12. Phase15 baseline is now in place:
   - the web export no longer aliases English and Korean `events.json` files to the same path; verification replay now hydrates the intended English stage scripts
   - the runtime can export a full `111`-stage replay suite, not just the currently active stage trace
   - `AW1.candidate_replay_suite.json`, `AW1.golden_capture_suite.json`, and `AW1.phase15_report.json` now provide a reproducible golden-baseline workflow
   - the current phase15 report is `111/111 pass`, `0` warnings, using exact spec checks plus replay-baseline comparison
13. Phase16 baseline is now in place:
   - Android release builds now enable shrink/minify, lint-vital, zipalign, and explicit WebView/network hardening
   - manifest now declares backup/data-extraction rules and disables cleartext traffic
   - release signing prefers env or `android/keystore.properties`, with a local debug-keystore fallback for machine-local verification
   - release APK assembly and installation were revalidated after hardening

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
