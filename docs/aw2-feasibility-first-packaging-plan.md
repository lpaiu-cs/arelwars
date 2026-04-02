# AW2 Feasibility-First Packaging Plan

Audit date: 2026-04-03

This plan replaces the blocked AW1 oracle path with a new target:

- decide first whether `arel_wars_2.apk` is realistically packageable in the current environment
- only then invest in the full original-equivalence and x64 packaging track

The goal is not to assume AW2 is easier.
The goal is to prove or disprove that assumption early.

## Core Rule

AW2 enters the full packaging track only if the original APK clears the feasibility gate.

If the feasibility gate fails, stop before large runtime-port work and record the blocker.

## Phase 0. APK Acquisition And Installability Gate

Goal:

- prove that the actual original `arel_wars_2.apk` exists locally and can be installed on the currently available emulator or desktop-supported Android environment

Required work:

- acquire the original APK file in the workspace
- inventory the APK:
  - manifest/package id
  - `native-code` ABI list
  - actual `lib/*` tree
  - min/target SDK
  - native library count and names
- attempt direct install on the current emulator
- if install fails, classify the failure:
  - no matching ABI
  - package parser/signing problem
  - SDK/version incompatibility
  - runtime dependency issue

Required artifacts:

- `apk_inventory.json`
- install attempt log
- package badging report
- ABI report

Approval criteria:

- the original APK file is present
- package metadata is extracted successfully
- the current emulator either:
  - installs the original APK successfully
  - or produces a precise, reproducible blocker

Go / no-go:

- `go`: original AW2 APK installs on the current emulator
- `no-go`: original AW2 APK cannot install in the current environment

Blocking condition:

- if Phase 0 is `no-go`, do not promise AW2 original-equivalence packaging

## Phase 1. Original Runtime Feasibility Probe

Goal:

- prove that the installed original AW2 package can actually boot far enough to be used as a runtime oracle

Required work:

- launch the original APK
- capture:
  - focused component
  - logcat
  - first screenshots
  - UI dump
  - audio activity snapshot
- determine whether the app:
  - crashes immediately
  - stalls in third-party bootstrap
  - reaches title/menu/first scene
  - runs under translation only partially

Required artifacts:

- probe session JSON
- screenshots
- UI XML
- logcat

Approval criteria:

- the original package launches
- the runtime reaches a stable observable scene
- the environment can at least capture scene transitions, screenshots, and package identity

Blocking condition:

- if the original package installs but cannot boot into a usable scene, AW2 packaging remains blocked

## Phase 2. Oracle And Capture Backend Gate

Goal:

- determine whether the current environment can produce useful oracle-grade evidence from the original AW2 runtime

Required work:

- probe:
  - package identity match
  - `run-as`
  - `su`
  - shell/profile tracing
  - accessible save roots
- define the strongest available backend for:
  - JNI trace
  - frame hashes
  - audio cues
  - save snapshots
  - scene transitions

Required artifacts:

- oracle capability report
- backend availability matrix

Approval criteria:

- the environment can produce an oracle session with the required trace schema, or
- the exact missing backend is isolated and documented while non-blocking evidence classes still work

Decision:

- `go`: enough oracle evidence can be captured to drive equivalence
- `limited-go`: partial oracle capture is possible; continue only if the missing fields can be recovered from runtime instrumentation
- `no-go`: package runs but cannot produce enough evidence to validate equivalence

## Phase 3. Static Bootstrap And Asset Truth Freeze

Goal:

- freeze the AW2 static truth layer before runtime-port work expands

Required work:

- extract and inventory:
  - `ZT1`
  - `PZD`
  - `PZF`
  - `PZA`
  - `PTC`
  - `MPL`
  - `GXL`/table data
- keep the current AW2 rule:
  - use `PZD` as the main image source
  - treat `PZF` as the state/timeline sidecar
  - do not assume AW1 `MPL` semantics
  - do not start from `img/*.pzx` unless `pc/*` is insufficient

Required artifacts:

- updated AW2 catalog
- script/table extraction
- binary asset report
- visual probe sheets for `PZD/PZF`

Approval criteria:

- the core static formats have machine-readable inventories
- `ZT1` scripts and table families are extractable
- `PZD` frames are previewable
- `PZF` variants are classified at least into stable families

## Phase 4. Packaging Architecture Decision

Goal:

- choose the actual packaging route based on Phase 0-3 evidence

Possible routes:

- `Route A`: original APK runs in current environment and can serve as oracle
  - pursue original-equivalence/x64 packaging
- `Route B`: original APK installs but oracle evidence is too weak
  - pursue compatibility port with explicit limits, not equivalence certification
- `Route C`: original APK does not install or boot
  - stop packaging work and keep AW2 as static reverse-engineering only

Required artifacts:

- route decision note
- decision rationale linked to prior phase artifacts

Approval criteria:

- one route is chosen explicitly
- the chosen route is defensible from the observed environment, not from optimism

## Phase 5. AW2 x64 Runtime Bootstrap

Precondition:

- Route A selected

Goal:

- build the minimal x64 runtime shell that can boot with original AW2 assets and expose the same capture points used by the oracle

Required work:

- mirror Java/native bootstrap expectations
- preserve original asset container usage where possible
- wire native library loading and lifecycle
- reach:
  - app launch
  - first surface init
  - first render or first meaningful scene

Required artifacts:

- debug APK
- runtime bootstrap logs
- launch screenshots

Approval criteria:

- the x64 path boots to the same early scene class as the original
- package identity and asset roots are known
- the runtime is instrumentable

## Phase 6. Runtime Trace Schema And Stage Bootstrap Fields

Precondition:

- Route A selected

Goal:

- make the x64 path emit the same machine-readable trace schema as the original AW2 oracle path

Required work:

- define AW2 trace fields
- instrument:
  - scene identity
  - stage or episode identity
  - route or branch labels
  - map binding if present
  - dialogue anchors
  - render/timing state cues
  - result/unlock flow
  - save slot and resume target

Required artifacts:

- x64 runtime trace JSON
- schema validation report

Approval criteria:

- original and x64 traces can be compared field-for-field without a separate manual adapter

## Phase 7. Representative Equivalence Pass

Precondition:

- Route A selected

Goal:

- prove one representative path first before scaling

Required work:

- choose one early stable AW2 scenario
- align:
  - launch path
  - scene progression
  - dialogue flow
  - render/timing witnesses
  - result path
  - lifecycle behavior

Required artifacts:

- oracle trace for one scenario
- x64 trace for the same scenario
- differential comparison report

Approval criteria:

- the representative scenario passes exact and bounded-tolerance checks
- there is no unexplained divergence in scene progression or restore behavior

## Phase 8. Save / Load And Lifecycle Equivalence

Precondition:

- Route A selected

Goal:

- align save/load semantics and background/resume behavior before final packaging

Required work:

- compare original and x64 behavior for:
  - save creation
  - load restore
  - resume target scene
  - relaunch continuity
  - orientation and home/resume

Required artifacts:

- save snapshots
- lifecycle trace pairs
- restore comparison report

Approval criteria:

- restore behavior is semantically equivalent
- no fallback-to-title or invalid resume jump remains

## Phase 9. Full Differential Suite

Precondition:

- Route A selected

Goal:

- scale the representative proof into a reusable approval suite

Required work:

- define the AW2 scenario matrix
- run original vs x64 comparisons
- classify mismatches into:
  - exact
  - tolerant
  - unsupported

Required artifacts:

- differential suite session JSON
- per-scenario reports
- summary verdict

Approval criteria:

- all mandatory scenarios pass
- unsupported scenarios are explicitly scoped out before packaging

## Phase 10. Packaging Gate

Precondition:

- Route A selected
- Phase 9 passed

Goal:

- produce and validate the final signed x64 AW2 APK

Required work:

- build release APK
- sign it
- install it
- rerun the final smoke matrix on the signed package

Required artifacts:

- signed APK
- signing verification output
- install verification output
- final packaging gate report

Approval criteria:

- signed APK reproduces the approved x64 trace outcomes
- no release-only regression appears

## Immediate Next Action

The next action is not reverse engineering.
It is Phase 0:

1. obtain the real `arel_wars_2.apk`
2. inspect its ABI layout
3. try direct install on the current emulator
4. decide whether AW2 is even eligible for the packaging track
