# AW1 Verification Protocol

This document defines how to compare the reconstructed AW1 runtime against the legacy `arel_wars_1.apk`.

## Goal

Produce stage-by-stage evidence that the remake matches the original in:

- stage identity
- map binding
- dialogue flow
- objective and wave flow
- result and unlock flow
- battle density within a bounded tolerance

## Canonical Inputs

- Verification spec:
  - [AW1.verification_spec.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.verification_spec.json)
- Runtime trace export:
  - exported from the remake UI with `Export Verification`
- Optional comparison report:
  - generated with [compare_aw1_verification_trace.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/compare_aw1_verification_trace.py)

## Required Exact Checks

- `familyId`
- `aiIndex`
- `routeLabel`
- `preferredMapIndex`
- `dialogueEventsSeen == scriptEventCount`
- stage result
- unlock target when a new node is revealed

## Required Sequence Checks

- victory path:
  - `deploy-briefing -> battle -> result-hold -> reward-review -> unlock-reveal? -> worldmap`
- defeat path:
  - `battle -> result-hold -> worldmap`
- objective phases:
  - compare ordered unique phase sequence from the trace

## Tolerant Checks

- dialogue anchor token overlap:
  - threshold `>= 0.75`
- wave counts:
  - drift `<= 1`
- spawn / projectile / effect / hero deploy metrics:
  - drift `<= 35%`

## Capture Procedure

1. Run the legacy APK for a target stage.
2. Capture one victory path and, when possible, one defeat path.
3. Record:
   - stage title
   - route label
   - preferred map index if visible or inferred
   - opening, midpoint, and closing dialogue anchors
   - ordered scene phases
   - ordered objective phases
   - allied/enemy wave counts
   - result and unlock target
4. Export the same stage trace from the remake runtime.
5. Compare both against the shared stage spec.

## Tooling

Generate the verification spec:

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_verification_spec.py \
  --runtime-blueprint /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json \
  --script-root /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/decoded/zt1/assets/script_eng \
  --output /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.verification_spec.json
```

Compare a remake trace against a legacy reference trace:

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/compare_aw1_verification_trace.py \
  --spec /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.verification_spec.json \
  --candidate /path/to/remake-trace.json \
  --reference /path/to/legacy-reference-trace.json \
  --output /path/to/comparison-report.json
```

## Notes

- The verification spec is stage-family based.
- Battle-density checks are intentionally tolerant. Structural mismatches must be fixed before density drift is tuned.
- The remake trace export is meant to be machine-readable, not just human-readable.
