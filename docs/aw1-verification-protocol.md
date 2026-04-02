# AW1 Verification Protocol

This document defines how to compare the reconstructed AW1 runtime against the legacy `arel_wars_1.apk`.

For the stricter original-equivalence transition plan, see [aw1-original-equivalence-certification-plan.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-original-equivalence-certification-plan.md).

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
- Native truth manifest:
  - [AW1.native_truth_manifest.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.native_truth_manifest.json)
- Original APK-derived reference bundle:
  - [AW1.original_reference_bundle.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_reference_bundle.json)
- Runtime trace export:
  - exported from the remake UI with `Export Verification`
- Full replay suite export:
  - exported from the remake UI with `Export Verification Suite`
  - current capture: [AW1.candidate_replay_suite.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json)
- Golden replay baseline:
  - [AW1.golden_capture_suite.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json)
- Optional comparison report:
  - generated with [compare_aw1_verification_trace.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/compare_aw1_verification_trace.py)
  - current phase15 report: [AW1.phase15_report.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.phase15_report.json)

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
5. Export the full replay suite from the remake runtime.
6. If a legacy trace is not currently obtainable on the machine, regenerate the replay golden suite from the exported candidate suite and compare against the shared stage spec.
7. When a legacy trace becomes available, swap it in as the reference trace without changing the stage spec.

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

Regenerate the replay-baseline golden suite from a verified candidate suite:

```bash
python3 /Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_golden_capture_suite.py \
  --spec /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.verification_spec.json \
  --runtime-blueprint /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json \
  --candidate-suite /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json \
  --output /Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json
```

## Notes

- The verification spec is stage-family based.
- Exact binding, dialogue count, anchors, and phase flow come from original APK-derived data in the spec.
- Tempo, wave density, battle metrics, and command overlap are checked against the replay golden suite so the regression path stays reproducible even when the legacy APK cannot be executed on the current machine.
- Battle-density checks are intentionally tolerant. Structural mismatches must be fixed before density drift is tuned.
- The remake trace export is meant to be machine-readable, not just human-readable.
- This protocol is still the regression-control layer. It is not, by itself, a full original-equivalence certification gate.
