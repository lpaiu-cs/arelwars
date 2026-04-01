# AW1 Stage Progression Notes

This note tracks the current best model for how AW1 story scripts and stage-definition rows line up.

Primary output:

- [AW1.stage_progression.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_progression.json)

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

## Next Steps

1. Use the correlation report to review candidate matches with weak token overlap but strong speaker/arc overlap.
2. Cross-reference candidate family ids against map/mission runtime data once `XlsMap` and related tables are better named.
3. Promote rows with strong evidence from `candidate` to `confirmed` mappings.
