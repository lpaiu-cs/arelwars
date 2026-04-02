# AW1 Behavioral Equivalence Criteria

Audit date: 2026-04-02

This document fixes the acceptance criteria for "original-behavior equivalence" of `arel_wars_1.apk` in a 64-bit environment.

It is intentionally stricter than "playable" or "compatible".
Passing means the 64-bit path preserves original executable intent, original asset usage, and original restore behavior closely enough that remaining differences are either zero or explicitly bounded.

## Scope

The target is not:

- a remake
- a best-effort compatible port
- a visually similar viewer

The target is:

- original `classes.dex` behavior model preserved
- original asset byte streams preserved
- original save semantics preserved
- original scene/state progression reproduced on a 64-bit runtime path

## Source Of Truth

The approval baseline is always the original APK and its original ARM native library:

- APK: `arel_wars1/arel_wars_1.apk`
- native library: `lib/armeabi/libgameDSO.so`

The current `disassemble` branch remains the source of truth for:

- native asset structure
- native parser behavior
- native call graph

The latest `main` outputs may be reused only as:

- search hints
- regression labels
- oracle trace field inspiration

They are not parser truth on their own.

## Hard Acceptance Rule

The 64-bit path passes only if all of the following hold:

1. original `classes.dex` launch and bridge expectations are preserved
2. original assets are used without substitute content
3. save/load semantics are preserved
4. required scenario traces match the original run in exact fields
5. ordered scene/state progression matches the original run
6. any tolerated drift stays within the bounded tolerances below
7. no unexplained divergence remains in stage binding, dialogue flow, result flow, unlock flow, or lifecycle restore behavior

## Required Scenario Set

The minimum approval suite is:

1. boot to title
2. title continue
3. menu save
4. menu load
5. battle entry
6. active battle for at least 30 seconds
7. retreat or defeat exit path
8. result flow
9. unlock reveal flow when applicable
10. orientation change during battle
11. home/background and resume
12. full app relaunch and restore from save

If a stage path does not expose a given branch, that branch is replaced with the nearest valid branch for the same stage family and noted explicitly in the trace.

## Required Exact Checks

The following fields are exact-match gates whenever they are defined for the captured run:

- `familyId`
- `aiIndex`
- `preferredMapIndex`
- `routeLabel`
- `dialogueEventsSeen == dialogueEventsExpected`
- `scene result`
- `unlock target`
- `save slot identity`
- `resume target scene`
- `resume target stage binding`

Exact means:

- no value drift
- no fallback remap
- no silent substitution

If one side cannot emit the field yet, the run is not considered passing.

## Required Sequence Checks

The following ordered sequences must match exactly:

- scene phase sequence
- objective phase sequence
- result/unlock flow
- lifecycle restore flow
- high-level audio cue order at scene boundaries

Scene-boundary audio cue order means:

- boot cue
- title cue
- menu cue
- battle cue
- result cue

The cue identity and order must match.

## Checkpoint Output Checks

Visual output is checked at stable checkpoints rather than every frame.

Stable checkpoints must include at least:

- title idle
- menu idle
- battle opening
- battle mid-run
- result screen
- resumed screen after lifecycle restore

Rules:

- static or mostly static checkpoints should match exactly by frame hash when capture conditions are controlled
- active battle checkpoints may use bounded drift metrics instead of full-frame identity when deterministic frame identity is not yet attainable
- any stable UI label, portrait assignment, stage title, or unlock target shown at the checkpoint must still match exactly

## Dialogue Anchor Checks

Each traced stage must capture dialogue anchors at:

- opening
- midpoint
- closing

The anchor text itself may differ only by formatting noise such as spacing or markup stripping.
The normalized token overlap threshold is:

- `>= 0.75`

Anything below that is a failure unless a parser-side normalization bug explains it.

## Tolerated Drift

Only the following drift is allowed:

- dialogue-anchor normalized token overlap: `>= 0.75`
- wave-count drift: `<= 1`
- spawn / projectile / effect / hero-deploy metric drift: `<= 35%`
- scene-boundary audio onset drift: `<= 1000 ms`

No other silent drift is accepted.

In particular, these are not tolerated:

- stage binding drift
- map choice drift
- result-type drift
- unlock-target drift
- save restore destination drift
- missing dialogue events

## Save Semantics Rule

Save compatibility is judged in two layers.

### 1. Required semantic equivalence

The restored game must preserve:

- active slot identity
- player/commander identity
- stage progression
- unlocked content
- active route or branch
- options that affect runtime behavior
- current or resumable scene
- battle result state when saved from result-hold or equivalent

### 2. Required format discipline

The 64-bit path must use the original save structure and meaning.

This means:

- no replacement save schema
- no lossy export/import transform
- no compatibility-only shadow save used as the real source of truth

Byte-identical save output is the preferred final standard.
Until volatile fields are fully identified, approval may rely on semantic equivalence plus documented exclusions.
Any excluded volatile fields must be named explicitly; implicit exclusions are not allowed.

## Lifecycle Rule

The 64-bit path must survive:

- pause/resume
- home/background
- orientation change
- full process relaunch after prior save

After restore, the following must remain correct:

- `familyId`
- `aiIndex`
- `preferredMapIndex`
- current scene phase
- audio state class
- save slot identity
- visible scene/output checkpoint

Crash-free resume is not enough.
The restored state must still be the original state.

## Failure Rules

The run fails immediately if any of the following occur:

- wrong `familyId`
- wrong `aiIndex`
- wrong `preferredMapIndex`
- missing or reordered critical scene phases
- missing dialogue events
- wrong result type
- wrong unlock target
- save/load changes the effective game state
- lifecycle restore lands in the wrong scene or wrong stage binding
- the system relies on substitute assets or substitute save meaning

## Evidence Package Required For Approval

Each approval run must leave behind:

- exact APK identity used
- exact native library identity used
- trace metadata
- scenario id
- checkpoint screenshots or hashes
- dialogue anchors
- scene phase sequence
- objective phase sequence
- result/unlock summary
- save artifact or save-field dump
- lifecycle restore evidence
- comparison verdict with exact failures and tolerated drift values

## Working Rule For Later Phases

If a future phase produces behavior that is only:

- plausible
- playable
- visually similar
- structurally close

that is not enough.

A phase is only approved when its outputs can be measured against the exact and tolerant gates in this document.

## Machine-Readable Spec

The matching machine-readable spec for tooling lives at:

- `recovery/arel_wars1/aw1_equivalence_spec.json`
