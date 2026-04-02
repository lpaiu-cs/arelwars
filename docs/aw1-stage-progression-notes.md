# AW1 Stage Progression Notes

This note tracks the current best model for how AW1 story scripts and stage-definition rows line up.

Primary output:

- [AW1.stage_progression.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_progression.json)
- [AW1.map_binding_candidates.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.map_binding_candidates.json)
- [AW1.inline_map_pointer_scan.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.inline_map_pointer_scan.json)
- [AW1.stage_map_proofs.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_map_proofs.json)
- [AW1.runtime_blueprint.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json)

## Current Model

There are three different index spaces in play:

1. `script family id`
   - derived from the first three digits of `assets/script_eng/*.zt1`
   - example: `0000`, `0001`, `0003`, `0004` all belong to family `000`
2. `XlsAi row index`
   - `130` English rows in [`XlsAi.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsAi.eng.parsed.json)
3. `XlsWorldmap` node index
   - `16` worldmap nodes in [`XlsWorldmap.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsWorldmap.eng.parsed.json)

The important conclusion is that `XlsWorldmap` is not the same index space as `XlsAi`.
`XlsWorldmap` is a compact overworld graph, while `XlsAi` is a much larger stage/scenario table.

## Strong Current Findings

- There are `111` script families.
- There are `130` `XlsAi` rows.
- `111` `XlsAi` rows have a matching script family id.
- `19` `XlsAi` rows do not have a matching script family id.
  - `10` of those are strong `ai-preset` candidates:
    - rows `120..129`
    - titles like `Very Poor - Aggressive`, `Normal - Defensive`, `Rich - Progressive`
  - the remaining `9` are currently `battle-only-or-unused` candidates.

This means `XlsAi` is not only a stage-title table. It also contains non-story scenario or AI-profile records.

## Runtime Field Findings

`AW1.stage_progression.json` now carries a compact runtime-field prefix for every script-backed stage row:

- `stageScalarCandidate`
- `tierCandidate`
- `variantCandidate`
- `regionCandidate`
- `constantMarkerCandidate`
- `storyFlagCandidate`

Current strongest reading:

- `regionCandidate`
  - high-confidence chapter or region bucket
  - story-backed rows cluster mostly into `5`, `6`, `7`, and `9`
- `tierCandidate`
  - medium-confidence progression tier
  - currently clusters into `10`, `20`, `30`, `50`
- `variantCandidate`
  - medium-confidence local encounter or map variant selector
  - small bounded range `1..6`
- `storyFlagCandidate`
  - medium-confidence binary story or cutscene toggle
  - alternates between adjacent rows in a way that looks like intro/outro or story-enabled variants

The strongest coarse story buckets so far are:

- `(tier=10, region=5)` early human-territory arc
- `(tier=10, region=6)` Juno/proxy arc
- `(tier=20/30/50, region=9)` late-game island/finale arc

## Provisional Correlation Rule

Current best working rule:

- `script family NNN` maps to candidate `XlsAi row NNN`

This is still provisional, but it is already useful enough to drive targeted verification.

## Why The Rule Is Plausible

### Family 000

- candidate `XlsAi[0] = First Battle`
- script packet:
  - `0000`
  - `0001`
  - `0003`
  - `0004`
- packet content includes:
  - prologue setup
  - first battle setup
  - basics-of-fighting tutorial

### Family 001

- candidate `XlsAi[1] = Buster Hunt`
- token overlap is weak, but the packet still looks like an early-stage follow-up cluster.

### Family 002

- candidate `XlsAi[2] = Seize Veril`
- script packet opens with:
  - `This must be the Beril.`
- spelling differs, but this is a strong practical match to `Veril/Beril`.

### Family 020

- candidate `XlsAi[20] = Meeting with Juno`
- token overlap is weak at the first lines, but the packet's major speakers include `Juno`.
- this is a good example of why the rule is useful but not yet fully proven.

### Family 028

- candidate `XlsAi[28] = Defeat Proxies`
- token overlap includes `proxies`
- packet context also lines up with the laboratory/proxy arc.

## Current Limits

- Script-family previews are not enough to prove a perfect one-to-one stage binding.
- Some titles only appear as later-story context, not in the first few lines.
- Some `XlsAi` rows are clearly not story-backed stages.
- `script family -> AI row` is much stronger than `AI row -> concrete map bin`.
- `XlsWorldmap` still looks like a separate overworld graph, not a direct stage table.

## Map Binding Candidates

`AW1.map_binding_candidates.json` remains the raw scratchpad for stage-to-map work.
`AW1.inline_map_pointer_scan.json` is the new proof scan that checks whether `XlsAi.numericBlock` already contains a compact inline map pointer.
`AW1.stage_map_proofs.json` is the structured layer that turns those findings into runtime-facing proof candidates.

Current strongest findings:

- `assets/map/*.zt1.bin` headers read cleanly as:
  - `version`
  - `layerCount`
  - `width`
  - `height`
  - reserved fields
  - `variantOrGroup`
- file sizes roughly follow:
  - `2 * layerCount * width * height + meta`
- `XlsMap` currently exposes `5` non-zero group pairs and `3` zeroed placeholder pairs.
- the most practical current hypothesis is:
  - `XlsMap` non-zero group pairs line up with map-bin pairs `000/001` through `008/009`
  - later map bins `010..015` are either unreferenced alternates, late-game-only maps, or attached through a different table path
- the current engine-facing bootstrap rule in [`AW1.stage_map_proofs.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_map_proofs.json) and [`AW1.runtime_blueprint.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json) is:
  - `variantCandidate 1 -> group 0 -> map pair 000/001`
  - `variantCandidate 2 -> group 1 -> map pair 002/003`
  - `variantCandidate 3 -> group 2 -> map pair 004/005`
  - `variantCandidate 4 -> group 3 -> map pair 006/007`
  - `variantCandidate 5/6 -> group 4 -> map pair 008/009`
  - `storyFlagCandidate` then chooses the preferred map inside the pair
- This is still heuristic, not a proven hard pointer, but it now carries an explicit support score, proof type, and evidence list instead of living only as a note.

## Inline Pointer Upgrade

The strongest current result is no longer only `variantCandidate -> template group`.

`AW1.inline_map_pointer_scan.json` now shows:

- `XlsAi.numericBlock byte[15]`
  - exact coverage `111/111`
  - compact mapping:
    - `1 -> 0`
    - `2 -> 2`
    - `3 -> 4`
    - `4 -> 6`
    - `5 -> 8`
    - `6 -> 8`
  - strongest reading: inline `pairBaseIndexCandidate`
- `XlsAi.numericBlock byte[18]`
  - exact coverage `111/111`
  - mapping:
    - `0 -> 0`
    - `1 -> 1`
  - strongest reading: inline `pairBranchIndexCandidate`
- combined formula:
  - `preferredMapIndex = pairBaseIndexCandidate + pairBranchIndexCandidate`
  - exact coverage `111/111`

This is still not a named source-level field from original code, but it is materially stronger than the earlier pure template heuristic.

## Runtime Blueprint Layer

[`AW1.runtime_blueprint.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json) is now the current integration boundary between reverse-engineering outputs and the Phaser runtime.

It adds three things on top of the raw reports:

1. `stageBlueprints`
   - one per script family / AI row candidate
   - includes stage title, reward text, hint text, runtime field tuple, scored map proof candidate, inline pair-base/branch pointer candidates, opcode cues, and recommended hero archetypes
2. `opcodeHeuristics`
   - now comes from `AW1.opcode_action_map.json`
   - promotes common `cmd-XX` clusters such as `cmd-02`, `cmd-05`, `cmd-06`, `cmd-08`, `cmd-0a`, `cmd-0b`, `cmd-43` into stable runtime labels with confidence levels and variant hints
3. `renderProfile`
   - carries the current default MPL bank rule, the special `179` packed-pixel rule, and the `PTC bridge` summary

This does not prove the final engine semantics, but it removes the need for the runtime to read multiple reverse-engineering reports directly.

## Next Steps

1. Use the runtime-field clusters to test whether `variantCandidate` or `regionCandidate` appears again in non-localized battle tables.
2. Cross-reference `AW1.map_binding_candidates.json` against battle/runtime payloads to prove which table actually points at concrete map bins.
3. Promote `script family -> AI row` links from `candidate` to `confirmed` as soon as a map or stage-control reference is found.
