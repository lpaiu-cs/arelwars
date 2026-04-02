# AW1 Main Branch Outputs Worth Reusing On `disassemble`

Audit date: 2026-04-02

This note re-audits `origin/main` from the `disassemble` point of view.
It only keeps `main` outputs that can help native tracing, native naming, or later oracle-style equivalence checks.

Reference points:

- previous `main` audit used on `disassemble`: `c302e2c`
- current `origin/main` audited here: `2018961`
- current common base with `disassemble`: `d0383b0`

The rule stays simple:

- keep `main` results that narrow a native search space or give a reusable regression/oracle label
- do not import `main`'s synthesized runtime sheets as byte-level native truth

## What Became Newly Useful After `c302e2c`

The latest `main` adds four classes of outputs that are genuinely useful on `disassemble`:

1. exact `script family -> XlsAi row -> map pair/branch` bindings
2. a more mature fixed-schema view of `GXL` runtime tables
3. stronger `particle / projectile / effect / hero-skill` cross-links
4. a full `111`-stage replay/golden verification corpus that can later serve as an ARM-oracle baseline

It also keeps older useful assets:

- regression stems `082`, `084`, `208`, `209`, `215`, `226`, `230`, `240`
- `MPL` bank switching
- `179` packed-pixel handling
- `PTC` emitter naming

## Keep As Strong Native Search Hints

### 1. Stage bootstrap and map selection

Primary files:

- `docs/aw1-stage-progression-notes.md`
- `recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json`
- `recovery/arel_wars1/parsed_tables/AW1.stage_progression.json`
- `recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json`

Useful facts:

- `111/111` script-backed stages now carry the same hard binding shape:
  - `int(script family id) == XlsAi row index`
  - `XlsAi numericBlock byte[15] -> pairBaseIndex`
  - `XlsAi numericBlock byte[18] -> pairBranchIndex`
  - `preferredMapIndex = pairBaseIndex + pairBranchIndex`
- `AW1.stage_bindings.json` records this as `hard-script-ai-inline-map` for all `111` current script-backed stages.
- `XlsAi` is no longer just “stage titles plus text”; on `main` it now behaves like a real stage-definition row with a stable prefix and an inline map-pointer pair.

Why this matters on `disassemble`:

- it gives a concrete native hunt target for the stage bootstrap path
- it suggests the original code likely keeps `script family id` and `XlsAi row index` aligned rather than translating through a large remap table
- it gives two exact candidate byte offsets inside the `XlsAi`-derived runtime payload that are worth tracing in native code

Recommended native follow-up:

- trace the stage loader and story bootstrap path for a direct `familyId -> rowIndex` use
- search for code that reads or copies the `XlsAi` numeric block and branches on offsets equivalent to byte `15` and byte `18`
- treat any native field that selects map pair or story branch as a high-priority naming target

### 2. Script opcode consumers

Primary files:

- `docs/aw1-script-opcode-notes.md`
- `recovery/arel_wars1/parsed_tables/AW1.opcode_action_map.json`
- `recovery/arel_wars1/parsed_tables/AW1.tutorial_opcode_chains.json`

Useful facts:

- `AW1.opcode_action_map.json` now covers all `64` observed non-dialogue opcode families with `unresolvedOpcodeCount = 0`
- the export distinguishes mnemonic-wide labels from variant-level labels instead of flattening them together
- the most useful tutorial/UI cluster is still:
  - `cmd-00(0x0d)`
  - `cmd-06(0x0d)`
  - `cmd-07..0e(0x40)`
- the exact tutorial-chain proof layer now tracks `15` raw-prefix needles

Why this matters on `disassemble`:

- it gives stable names for the script/runtime consumers you will see before the grammar is fully native-confirmed
- the `0x40` family is a very good target when hunting the native tutorial-focus or HUD-highlight consumer
- the split between “mnemonic label” and “variant label” is the right caution level for disassembly notes too

Recommended native follow-up:

- prioritize native consumers for the `0x40` tutorial-target family before low-frequency opcodes
- keep raw-prefix forms such as `060d0740`, `060d0a40`, `000d0440` as regression needles when following script VM dispatch
- do not rename opcode fields from `main` one-to-one unless the native parser proves the same argument grammar

### 3. GXL-derived runtime schemas

Primary files:

- `docs/aw1-gxl-table-notes.md`
- `recovery/arel_wars1/parsed_tables/AW1.engine_schema.json`
- `recovery/arel_wars1/parsed_tables/AW1.hero_runtime_families.json`
- `recovery/arel_wars1/parsed_tables/AW1.hero_runtime_archetypes.json`

Useful facts:

- `AW1.engine_schema.json` now stabilizes eight table families into one export:
  - `units = 55`
  - `heroes = 6`
  - `heroAiProfiles = 12`
  - `skillAiProfiles = 24`
  - `projectiles = 35`
  - `effects = 37`
  - `particles = 12`
  - `balance = 4`
- `main`'s current best candidates for runtime-relevant fixed tables are:
  - `XlsHero_Ai`
  - `XlsSkill_Ai`
  - `XlsProjectile`
  - `XlsEffect`
  - `XlsParticle`
- `AW1.hero_runtime_families.json` and `AW1.hero_runtime_archetypes.json` do not prove native wire format, but they do cluster the hero-skill tables into concrete runtime channels such as:
  - `Dispatch`
  - `Defend Tower / Tower Defense`
  - `Recall`
  - `Mana Gain`
  - `Mana Wall`
  - `Armageddon`

Why this matters on `disassemble`:

- it narrows which `data_*.zt1` families are most worth tracing in native code first
- it gives row counts and candidate struct widths that are useful when identifying loader loops, table caches, or memcpy blocks
- it turns anonymous battle-runtime fields into named search targets

Recommended native follow-up:

- prioritize native loaders that populate projectile/effect/particle and hero-AI/skill-AI tables
- look for loops whose iteration counts plausibly match `12`, `24`, `35`, or `37`
- when you hit a battle runtime object with repeated small arrays, test against these table counts before inventing a new schema

### 4. Effect, projectile, and PTC cross-links

Primary files:

- `recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json`
- `recovery/arel_wars1/parsed_tables/AW1.render_pack.json`
- `recovery/arel_wars1/parsed_tables/AW1.render_semantics.json`

Useful facts:

- `XlsParticle` now looks like the strongest current compact `PTC` bridge table:
  - primary direct `PTC` hit count: `12/12`
  - nonzero secondary direct `PTC` hit count: `10/10`
- `PTC 048` is reused across several rows, which looks like a shared emitter template with alternate secondary layers
- `XlsHeroActiveSkill.tailPairBE` yields exact runtime-table hits in `5/25` rows
- concrete exact matches already exported on `main` include:
  - pair `(4, 1)` -> projectile row `5`
  - pair `(3, 2)` -> effect row `26`
  - pair `(3, 0)` -> projectile row `4` and effect row `24`
- `AW1.render_pack.json` adds reusable emitter names for those bridges, such as:
  - `support-pulse`
  - `burst-flare`
  - `impact-spark`
  - `utility-trail`

Why this matters on `disassemble`:

- it strongly suggests that at least part of hero active-skill tail data is a direct effect/projectile reference block
- it gives a concrete bridge from `data_*.zt1` tables to `ptc/*.ptc` assets
- it makes `PTC` consumers and effect launchers easier to label once you find them natively

Recommended native follow-up:

- trace hero-active-skill consumption into projectile/effect spawn paths before spending more time on higher-level heuristics
- prioritize native code that bridges battle-skill tables to `PTC` or effect-player objects
- keep `PTC 048`, `046/034`, `047/043`, and `034/022` as named regression anchors

## Keep As Native-Consistent Labels

These were already useful before, and the latest `main` still reinforces them:

- `recovery/arel_wars1/parsed_tables/AW1.render_semantics.json`
- `recovery/arel_wars1/parsed_tables/AW1.render_pack.json`

Still safe to reuse:

- `MPL` selector rule:
  - `flag == 0 -> bank B`
  - `flag > 0 -> bank A`
- `179` stays a special packed-pixel path:
  - `0` transparent
  - normalize with `value - 1`
  - `47`-color core band
  - `189..199` additive highlight tail
- `PTC` emitter names are useful note labels even when their runtime scheduling stays partly heuristic

Why this matters on `disassemble`:

- these labels help document native consumers without forcing a false parser claim
- `179` should still be isolated as a one-off render path when tracing packed-pixel draw code

## Keep As Oracle / Regression Material

Primary files:

- `docs/aw1-verification-protocol.md`
- `recovery/arel_wars1/parsed_tables/AW1.verification_spec.json`
- `recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json`
- `recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json`

Useful facts:

- both replay suites currently carry `111/111` completed traces
- the trace format already includes:
  - `familyId`
  - `aiIndex`
  - `preferredMapIndex`
  - dialogue anchors
  - scene command ids
  - scene phase sequence
  - objective phase sequence
  - result/unlock flow

Why this matters on `disassemble`:

- this is not parser truth, but it is excellent equivalence-oracle material
- once an ARM runner or native call harness exists, these traces can be used to compare real original execution against reconstructed runtime behavior
- it gives a ready-made list of stage/story/script states worth instrumenting in native code

Recommended future use:

- when tracing JNI or story progression code, reuse the `111`-stage suite as the validation target set
- use the trace fields as the first machine-readable output schema for any future native/original-run capture tool

## Carry Forward From The Previous Audit

These older `main` assets are still worth keeping open:

- regression stems:
  - `082`
  - `084`
  - `208`
  - `209`
  - `215`
  - `226`
  - `230`
  - `240`
- `docs/arel_wars1-recovery.md`
- `recovery/arel_wars1/timeline_candidate_strips/*.json`
- `recovery/arel_wars1/frame_meta_group_probes/*.png`

Use them for:

- choosing sample stems
- separating base-linked versus overlay-only behavior
- keeping visual regression targets around while tracing native consumers

Do not use them for:

- promoting heuristic tail cadence into a native field grammar
- treating donor/prototype timing as recovered binary truth

## Do Not Import As Native Truth

The latest `main` still contains many useful runtime syntheses.
They are not disassemble-side ground truth.

Do not promote these directly into native format claims:

- `AW1.runtime_blueprint.json`
- `AW1.battle_model.json`
- `AW1.hero_runtime_archetypes.json`
- `AW1.phase15_report.json`
- `docs/aw1-1to1-restoration-plan.md`
- Android-port and verification-flow docs from late `main` phases

Reason:

- they are engine-facing, validation-facing, or remake-facing syntheses
- they often sit one layer above the binary structures `disassemble` is trying to close
- they are valuable as names and oracle fields, not as parser specs

## Immediate Disassemble Actions Enabled By The Latest `main`

1. Add a native tracing target for the stage bootstrap path that can prove or reject:
   - `script family id == XlsAi row index`
   - `numericBlock byte[15]` as map-pair selector
   - `numericBlock byte[18]` as branch bit
2. Prioritize native loaders/consumers for:
   - `XlsHero_Ai`
   - `XlsSkill_Ai`
   - `XlsProjectile`
   - `XlsEffect`
   - `XlsParticle`
3. Follow hero active-skill tail consumers into projectile/effect/PTC launch paths using the exported exact-hit pairs.
4. Keep the `0x40` tutorial/UI prefix family high on the script-VM tracing list.
5. Reuse the `111`-stage replay/golden suites as the future oracle schema for any ARM-run differential harness.

## Working Rule

When a `main` artifact says:

- “this exact index, byte offset, row count, or asset bridge recurs across the whole data set”

it is usually worth feeding into `disassemble` as a native search hint.

When it says:

- “this creates a plausible runtime behavior or scene layer”

keep it as a regression label or oracle field until a native consumer proves the same thing.

Related note:

- `docs/aw1-main-branch-correction-hints.md` remains the hand-off note for `main` workers
