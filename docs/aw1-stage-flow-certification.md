# AW1 Stage Flow Certification

This document records the full structural-flow certification pass for all `111` AW1 stages.

Primary artifact:

- [AW1.stage_flow_certification.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_flow_certification.json)

Generator:

- [export_aw1_stage_flow_certification.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_stage_flow_certification.py)

Inputs:

- [AW1.original_reference_bundle.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json)
- [AW1.side_by_side_report.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.side_by_side_report.json)
- [AW1.candidate_replay_suite.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json)
- [AW1.golden_capture_suite.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json)

## Certification Rule

A stage is `certified` when its stage-flow comparison has:

- zero `exact` mismatches
- zero `tolerant` mismatches

The certification focuses on:

- hard stage binding
- dialogue event count
- dialogue anchor coverage
- scene phase sequence
- objective progression
- result
- unlock reveal routing

## Command

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_stage_flow_certification.py \
  --reference-bundle /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json \
  --side-by-side /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.side_by_side_report.json \
  --candidate-suite /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json \
  --reference-suite /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json \
  --output /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_flow_certification.json
```

## Current Meaning

When this report shows:

- `certifiedStageCount == 111`
- `blockedStageCount == 0`
- `unresolvedStructuralMismatchCount == 0`

the project has passed the `full stage flow` certification layer.

This still does not finish battle-equivalence or render-equivalence certification. It only proves that stage identity, dialogue order, scene phases, result, and unlock flow are structurally aligned across the full campaign.
