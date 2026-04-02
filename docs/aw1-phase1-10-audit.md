# AW1 Phase 1-10 Audit

This file records a re-review of the user-defined AW1 approval phases 1 through 10.
It exists to separate:

- what is approved in the current repository state
- what evidence supports that approval
- what is still missing, but belongs to later phases rather than invalidating phases 1-10

Audit date: 2026-04-02

## Scope

The audited phases are the user-defined sequence:

1. deterministic battle engine migration
2. concrete unit/projectile/effect/resource/AI runtime rules
3. battle result resolution from actual battle state
4. fixed engine input schema from recovered AW1 tables
5. hard binding of script family, `XlsAi`, and map bin
6. full non-dialogue `ZT1` opcode naming and scene interpreter completion
7. replacement of cue-beat glue with explicit scene script steps
8. final recovered render pack for `PZX/MPL/PTC/179`
9. fixed `179` blend model, `MPL` bank semantics, and `PTC` emitter semantics
10. battle-time sprite state, hit flash, burst, particle, camera shake, and overlay linkage

## Decision Rule

A phase is marked `approved` when the current repo contains:

- runtime code consuming the recovered data directly
- generated artifacts proving the same path exists in exported recovery data
- a successful current build

This is not the same as full original-device validation.
Original-behavior proof against legacy capture remains a later validation phase.

## Audit Result

### Phase 1

Status: `approved`

Evidence:

- deterministic entity-step combat core in [RecoveryStageSystem.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/systems/recoveryStageSystem.ts)
- commit baseline:
  - `4629304` `Replace AW1 lane preview with deterministic entity core`
- current runtime no longer routes battle through a pressure-only preview loop

Residual note:

- entity rules are reconstruction rules, not yet legacy-reference tuned

### Phase 2

Status: `approved`

Evidence:

- recovered battle model input in [AW1.battle_model.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_model.json)
- unit/projectile/effect/resource/AI rule consumption in [RecoveryStageSystem.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/systems/recoveryStageSystem.ts)
- hardening commits:
  - `3c86b5d` `Implement AW1 phase 2 battle runtime rules`
  - `e1f94c2` `Harden AW1 phase 2 battle rule paths`

Evidence summary:

- unit entity, movement, collision, tower hit, death cleanup, spawn gating, projectile, effect, cooldown, resource, and AI tick are all live
- direct tower HP changes are routed through shared helpers
- direct spawns respect population caps unless scene seeding intentionally bypasses them

### Phase 3

Status: `approved`

Evidence:

- result logic in [RecoveryStageSystem.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/systems/recoveryStageSystem.ts)
- commit:
  - `52c11a5` `Replace AW1 battle resolution heuristics`

Evidence summary:

- battle resolution no longer keys off lane-pressure-only momentum thresholds
- victory and defeat read tower collapse, field clearance, dispatched wave exhaustion, secured lanes, and queue/mana exhaustion

Residual note:

- `objectiveProgressRatio` still exists for scene flow and HUD pacing, but it is no longer the primary result oracle

### Phase 4

Status: `approved`

Evidence:

- canonical schema export [AW1.engine_schema.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.engine_schema.json)
- summary:
  - `unitCount=55`
  - `heroCount=6`
  - `heroAiProfileCount=12`
  - `skillAiProfileCount=24`
  - `projectileCount=35`
  - `effectCount=37`
  - `particleCount=12`
  - `balanceRowCount=4`
- commit:
  - `c30b5ed` `Fix AW1 canonical engine schema inputs`

### Phase 5

Status: `approved`

Evidence:

- hard binding export [AW1.stage_bindings.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json)
- summary:
  - `stageBindingCount=111`
  - `scriptAiExactCoverage=111`
  - `inlineMapExactCoverage=111`
  - `bindingTypeHistogram.hard-script-ai-inline-map=111`
- commit:
  - `bc1aefd` `Hard-bind AW1 stage families to map bins`

### Phase 6

Status: `approved`

Evidence:

- opcode export [AW1.opcode_action_map.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.opcode_action_map.json)
- summary:
  - `opcodeActionCount=64`
  - `featuredOpcodeCount=15`
  - `curatedVariantCount=184`
  - `unresolvedOpcodeCount=0`
- scene interpreter path in [RecoveryStageSystem.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/systems/recoveryStageSystem.ts)
- commit:
  - `e4385bc` `Complete AW1 phase 6 scene command interpreter`

Residual note:

- names are now stable reconstructed command names; later reference validation may still rename them closer to the original engine’s intent

### Phase 7

Status: `approved`

Evidence:

- compiled `sceneScriptSteps[]` execution path in [RecoveryStageSystem.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/systems/recoveryStageSystem.ts)
- commit:
  - `519e7cd` `Replace AW1 cue beats with scene script steps`

Evidence summary:

- runtime executes explicit directives for objective, panel, wave, spawn, dispatch, mana, notes, and scripted actions
- direct cue-switch execution was replaced by step compilation plus step interpretation

### Phase 8

Status: `approved`

Evidence:

- render pack [AW1.render_pack.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.render_pack.json)
- summary:
  - `stemCount=21`
  - `bankProbeCount=7`
  - `packedSpecialCount=1`
  - `emitterPresetCount=12`
- runtime consumption in [RecoveryBootScene.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/scenes/RecoveryBootScene.ts)
- commit:
  - `0d79403` `Finalize AW1 recovered render pack`

### Phase 9

Status: `approved`

Evidence:

- render semantics export [AW1.render_semantics.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.render_semantics.json)
- summary:
  - `bankStateCount=224`
  - `ptcEmitterCount=12`
  - `packedPixelSpecialCount=1`
- fixed semantics:
  - `179` transparency and `value - 1` normalized four-band palette rule
  - exact `MPL` flag-driven bank switching
  - named `PTC` emitter semantics
- commit:
  - `f62cba4` `Finalize AW1 phase 9 render semantics`

### Phase 10

Status: `approved`

Evidence:

- battle-time render-state linkage in:
  - [RecoveryStageSystem.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/systems/recoveryStageSystem.ts)
  - [RecoveryBootScene.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/scenes/RecoveryBootScene.ts)
  - [recovery-types.ts](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/src/recovery-types.ts)
- commit:
  - `a84238a` `Connect AW1 battle events to render states`

Evidence summary:

- battle events now emit:
  - sprite state
  - hit flash
  - burst pulse
  - particle boost
  - camera shake
  - overlay pulse
- scene rendering consumes those states directly for entity/effect visuals

Residual note:

- “원본처럼” is satisfied at the reconstruction-runtime level, not yet by side-by-side legacy footage validation

## Re-Review Conclusion

No blocking implementation gap was found that invalidates phases 1 through 10.

The remaining risks are all later-phase risks:

- original-reference validation
- remaining UX flow completion
- save/load and audio
- release hardening
- full campaign equivalence proof

That means phases 1-10 remain approved, and the next unresolved work starts after them rather than inside them.
