# AW1 Original-Equivalence Certification Plan

This document defines the work needed to move from “phase-complete reconstruction” to “certified against the original APK.”

It is intentionally stricter than the current replay/golden protocol.

## Goal

Prove that the reconstructed AW1 runtime matches the original `arel_wars_1.apk` closely enough to call it behaviorally equivalent under fixed inputs.

That proof must be based on original-side reference traces, not only on remake-generated golden captures.

## Entry Conditions

These are already in place:

- phase-based restoration runtime exists
- `111` stage bindings are hard-linked
- opcode registry exists
- battle/runtime/render exports exist
- native/disassemble corrections have been reviewed
  - [aw1-disassemble-branch-review.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md)
  - [aw1-native-branch-alignment.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-native-branch-alignment.md)

## Certification Principles

### Native Truth Wins

Use native-confirmed sources as ground truth when available:

- `PZA` for base clip timing
- `PZF` for frame composition
- `PZD` for image-pool indexing
- exact stage binding from `script family -> XlsAi -> inline map pointer`

### Heuristic Runtime Data Stays Secondary

The following may remain useful for the remake runtime, but they are not certification truth by themselves:

- `timelineKind`
- `playbackDurationMs`
- grouped tail cadence
- donor/prototype timing fills
- replay goldens generated only from the remake

### Compare Original To Remake, Not Remake To Itself

Current phase-15 replay goldens remain useful as a regression safety net, but original-equivalence certification must compare:

- original APK traces
- remake traces

for the same stage, route, and input script.

## Work Stages

### Stage 0. Freeze Native Reference Inputs

Deliverables:

- branch review note
- native alignment note
- selected disassemble tools mirrored or callable from `main`

Required artifacts:

- `compare_main_regression_set.py`
- native loader notes for `PZA/PZF/PZD`
- native timing notes for `CGxPZxAni`

Exit condition:

- the team agrees which fields are `native-confirmed` and which remain heuristic

### Stage 1. Build A Native Reference Bundle

For each target stage, capture or derive:

- stage identity
- route label
- map binding
- dialogue order
- scene command sequence
- base clip timing from `PZA`
- frame composition from `PZF`
- battle result
- unlock transition

Outputs:

- original-side trace schema
- original-side capture bundle directory
- conversion tools that normalize legacy captures into the same schema the remake exports

Exit condition:

- at least the regression stems have normalized original traces

### Stage 2. Add A Side-By-Side Comparator

Build a comparator that classifies mismatches into:

- `binding`
- `dialogue`
- `scene-command`
- `timing`
- `battle`
- `render`
- `result`
- `unlock`

The comparator should separate:

- exact mismatches
- tolerance-window mismatches
- heuristic-layer mismatches that do not yet fail certification

Exit condition:

- machine-readable comparison report exists for one stage and one regression stem

### Stage 3. Certify The Regression Stem Set First

Use the eight known stems first:

- `082`
- `084`
- `208`
- `209`
- `215`
- `226`
- `230`
- `240`

Focus:

- `PZA` base timing
- `PZF` frame order
- render-state transitions
- grouped-tail divergence from native timing

Exit condition:

- no unresolved structural mismatch on the regression set

### Stage 4. Certify Stage Flow Across All 111 Stages

For every stage:

- dialogue order must match
- scene phase sequence must match
- objective progression must match
- battle result must match
- unlock reveal / next-node routing must match

Exit condition:

- all `111` stages pass structural flow checks

### Stage 5. Certify Battle Equivalence

For selected representative stages per route/profile:

- same deploy loadout
- same route
- same input script
- compare:
  - spawn counts
  - hero deploy timing
  - projectile/effect counts
  - tower HP trend
  - victory/defeat timing window

Exit condition:

- representative battle set passes exact/tolerant thresholds agreed in the protocol

### Stage 6. Certify Render/Event Equivalence

For the same representative set:

- sprite state changes
- bank switching
- `179` special rendering
- hit flash
- burst overlays
- particle activity
- camera shake

Exit condition:

- no unresolved native-confirmed render mismatch remains

### Stage 7. Final Certification Gate

The project can claim original-equivalence certification only when all are true:

- regression stems certified
- all `111` stages pass structural flow comparison
- representative battle set passes battle comparison
- representative render set passes render comparison
- no remaining mismatch is hidden behind a heuristic-only label without explicit waiver

## Recommended First Tasks

1. Mirror or port the disassemble-side regression comparator onto `main`.
2. Extend [aw1-verification-protocol.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-verification-protocol.md) with an explicit `native reference trace` mode.
3. Define the original-side trace JSON schema.
4. Run the regression stem set before touching all `111` stages.

## Relationship To The Current Verification Protocol

[aw1-verification-protocol.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-verification-protocol.md) remains valid for remake regression control.

This document is stricter. It covers the next step:

- certifying the remake against the original APK
- not only against remake-side stage specs and replay goldens
