# AW1 Regression Stem Certification

This document records the first certification pass for the regression stem set:

- `082`
- `084`
- `208`
- `209`
- `215`
- `226`
- `230`
- `240`

Primary artifact:

- [AW1.regression_stem_certification.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.regression_stem_certification.json)

Generator:

- [export_aw1_regression_stem_certification.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_regression_stem_certification.py)

Inputs:

- [AW1.native_truth_manifest.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.native_truth_manifest.json)
- [AW1.original_reference_bundle.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json)
- [AW1.side_by_side_report.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.side_by_side_report.json)
- [preview_manifest.json](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/public/recovery/analysis/preview_manifest.json)
- [AW1.runtime_blueprint.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json)

## Certification Rule

A regression stem is `certified` when:

- `PZD` structure matches
- `PZF` frame-composition structure matches
- `PZA` base timing source is present and native-confirmed
- no `exact` or `tolerant` mismatches remain in the side-by-side comparator

It may still carry explicit heuristic waivers for:

- `timelineKindConfidence`
- `overlayCadenceConfidence`

These do not block certification because they are already marked as heuristic layers in:

- [AW1.native_truth_manifest.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.native_truth_manifest.json)

## Command

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_regression_stem_certification.py \
  --native-truth /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.native_truth_manifest.json \
  --reference-bundle /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json \
  --side-by-side /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.side_by_side_report.json \
  --preview-manifest /Users/lpaiu/vs/others/arelwars/remake/arel-wars1/public/recovery/analysis/preview_manifest.json \
  --runtime-blueprint /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json \
  --output /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.regression_stem_certification.json
```

## Current Meaning

When this report shows:

- `blockedStemCount == 0`
- `unresolvedStructuralMismatchCount == 0`

the regression stem set is certified for the current bootstrap certification stage.

This does not certify all `111` stages yet. It only proves that the high-risk render/timing stems are structurally aligned with the current original-side bundle.
