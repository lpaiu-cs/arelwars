# AW1 Original Reference Bundle

This document describes the APK-derived reference bundle used as the first original-side input for equivalence certification.

Primary artifact:

- [AW1.original_reference_bundle.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json)

## Purpose

The bundle freezes two things from the original APK side:

- `111` stage-flow references
- `8` regression-stem render/timing references

It is the bridge between:

- original APK assets and native-confirmed loader findings
- remake-side verification and future side-by-side certification

## What It Contains

### Stage References

For each stage:

- stage identity
- hard `script family -> XlsAi -> map bin` binding
- dialogue anchors
- expected victory path
- expected defeat path
- scene-command reference cues

### Regression Render References

For stems:

- `082`
- `084`
- `208`
- `209`
- `215`
- `226`
- `230`
- `240`

the bundle stores:

- typed `PZX` root graph
- `PZD` type/image summary
- `PZF` resource summary
- embedded `PZA` clip timing and frame-index sequences

## Important Limitation

This bundle is `original APK-derived`, but it is not yet `live legacy runtime capture`.

That distinction matters:

- it is strong enough for reference structure and native-aligned animation truth
- it is not the final proof of runtime equivalence

Later certification stages still need:

- original-side runtime traces
- side-by-side comparison against remake traces

## Generation

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_original_reference_bundle.py \
  --apk /Users/lpaiu/vs/others/arelwars/arel_wars1/arel_wars_1.apk \
  --verification-spec /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.verification_spec.json \
  --stage-bindings /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json \
  --runtime-blueprint /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json \
  --native-truth /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.native_truth_manifest.json \
  --output /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json
```

## Relationship To Other Artifacts

- [AW1.native_truth_manifest.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.native_truth_manifest.json)
  - defines what counts as native truth versus heuristic
- [AW1.verification_spec.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.verification_spec.json)
  - defines stage-by-stage comparison checkpoints
- [aw1-original-equivalence-certification-plan.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-original-equivalence-certification-plan.md)
  - defines how this bundle is used in later certification stages
