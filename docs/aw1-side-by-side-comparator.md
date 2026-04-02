# AW1 Side-By-Side Comparator

This document describes the `original vs remake` comparator used in the certification track.

Primary inputs:

- original reference bundle:
  - [AW1.original_reference_bundle.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json)
- remake candidate verification suite:
  - [AW1.candidate_replay_suite.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json)
- normalized original trace suite:
  - [AW1.golden_capture_suite.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json)
- remake runtime inputs:
  - [AW1.runtime_blueprint.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json)
  - [preview_manifest.json](/Users/lpaiu/vs/others/arelwars/remake/arel-wars1/public/recovery/analysis/preview_manifest.json)

Comparator tool:

- [compare_aw1_side_by_side.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/compare_aw1_side_by_side.py)

Current bootstrap output:

- [AW1.side_by_side_report.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.side_by_side_report.json)

## Categories

The comparator classifies mismatches into:

- `binding`
- `dialogue`
- `scene-command`
- `timing`
- `battle`
- `render`
- `result`
- `unlock`

Each mismatch is also tagged as one of:

- `exact`
- `tolerant`
- `heuristic`

`exact` mismatches fail a stage or regression-stem comparison.

`tolerant` mismatches downgrade a comparison to `warn`.

`heuristic` mismatches remain visible in the report but do not fail certification by themselves.

## Bootstrap Mode

The current comparator can run in two modes:

- `normalized-original-trace-suite`
  - uses a normalized original-side trace suite together with the APK-derived bundle
- `bundle-only-bootstrap`
  - uses only the APK-derived bundle and limits timing/battle comparisons accordingly

Until live legacy captures are available, the preferred bootstrap input remains:

- [AW1.golden_capture_suite.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json)

## Command

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/compare_aw1_side_by_side.py \
  --reference-bundle /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json \
  --candidate-suite /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json \
  --reference-suite /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json \
  --runtime-blueprint /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json \
  --preview-manifest /Users/lpaiu/vs/others/arelwars/remake/arel-wars1/public/recovery/analysis/preview_manifest.json \
  --output /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.side_by_side_report.json
```

## Notes

- stage comparisons are driven by hard bindings, dialogue anchors, command sets, phase sequences, result, and unlock routing
- regression-stem comparisons are driven by native `PZD/PZF/PZA` structure and remake preview timing/render metadata
- this comparator is a certification tool, not a runtime gameplay validator
