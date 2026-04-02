# AW1 Battle/Render Equivalence Certification

This document defines the representative-set certification step that sits between full stage-flow certification and the final original-equivalence gate.

## Goal

Prove that the remake matches the original-equivalence reference not only in stage flow, but also in:

- battle density and tempo
- tower HP trends
- wave dispatch counts
- representative render-state behavior

using a small but coverage-driven set of stages and the known regression render stems.

## Representative Battle Set

The battle set is selected greedily from [AW1.runtime_blueprint.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json).

Coverage targets:

- routes:
  - `primary`
  - `secondary`
- effect intensities:
  - `low`
  - `medium`
  - `high`
- core combat archetypes:
  - `dispatch`
  - `tower-defense`
  - `naturalhealing`
  - `recall`
  - `manawall`
  - `armageddon`
  - `managain`
  - `special-stun`

Current selected set:

- `000` `First Battle`
- `009` `Reclaim Iron`
- `033` `Aerial Attacks`

## Battle Checks

Exact:

- `result`
- `preferredMapIndex`
- `tempoBand`

Tolerant:

- `alliedWavesDispatched`
- `enemyWavesDispatched`
  - absolute drift `<= 1`
- `spawnCount`
- `projectileCount`
- `effectCount`
- `heroDeployCount`
  - density drift `<= 35%`
- `alliedTowerMinHpRatio`
- `enemyTowerMinHpRatio`
  - absolute drift `<= 0.15`
- `elapsedMs`
  - `<= max(5000ms, 5%)`

## Representative Render Set

Representative render certification reuses the known regression render hotspots:

- `082`
- `084`
- `208`
- `209`
- `215`
- `226`
- `230`
- `240`

These remain the native-confirmed structural set for:

- `PZA` base timing
- `PZF` frame composition
- `PZD` image-pool layout
- `MPL` bank switching

The representative battle stages add witness coverage for:

- route-dependent render intent
- low/medium/high effect intensity
- packed special handling path visibility

## Blocking Conditions

Battle certification blocks on:

- any exact mismatch
- any tolerant mismatch

Render certification blocks on:

- any blocked regression render stem
- any unresolved native-confirmed render mismatch
- missing native-confirmed MPL bank switching rule
- missing `179` packed-pixel special

Non-blocking render witness:

- `PTC` emitter semantics remain `runtime-consistent heuristic`

## Outputs

- report:
  - [AW1.battle_render_certification.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_render_certification.json)
- exporter:
  - [export_aw1_battle_render_certification.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_battle_render_certification.py)

## Command

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_battle_render_certification.py \
  --side-by-side /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.side_by_side_report.json \
  --stage-flow-certification /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_flow_certification.json \
  --regression-certification /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.regression_stem_certification.json \
  --runtime-blueprint /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json \
  --render-pack /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.render_pack.json \
  --render-semantics /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.render_semantics.json \
  --candidate-suite /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json \
  --reference-suite /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json \
  --output /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_render_certification.json
```
