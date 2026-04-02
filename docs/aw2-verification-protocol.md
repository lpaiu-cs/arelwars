# AW2 Verification Protocol

Audit date: 2026-04-03

This document defines the oracle-capture structure for the original `arel_wars_2.apk`.

Its purpose is narrower than full equivalence.
It fixes:

- what must be captured from an original AW2 run
- which backends are acceptable
- which top-level field structure the oracle session must use
- what to do when the environment can run the APK but not expose every backend

## Goal

Produce a reference trace from the original AW2 APK that includes:

- package identity
- JNI trace backend result
- frame hashes
- save-file evidence
- audio-cue evidence
- scene-transition evidence
- a verification-trace object usable by later differential tooling

## Canonical Inputs

- original APK:
  - [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk)
- feasibility track plan:
  - [aw2-feasibility-first-packaging-plan.md](/C:/vs/other/arelwars/docs/aw2-feasibility-first-packaging-plan.md)
- installability gate:
  - [aw2-phase0-installability-gate.md](/C:/vs/other/arelwars/docs/aw2-phase0-installability-gate.md)
- static bootstrap note:
  - [arel_wars2-bootstrap.md](/C:/vs/other/arelwars/docs/arel_wars2-bootstrap.md)

## Output Structure

The capture harness writes one session JSON with these top-level sections:

- `specVersion`
- `captureId`
- `packageName`
- `device`
- `oracleTarget`
- `capabilities`
- `artifacts`
- `jniCallTrace`
- `frameHashes`
- `audioCues`
- `sceneTransitions`
- `saveSnapshots`
- `verificationTrace`

Minimum fields in `verificationTrace`:

- `traceId`
- `familyId`
- `aiIndex`
- `stageTitle`
- `storyboardIndex`
- `routeLabel`
- `preferredMapIndex`
- `scriptEventCountExpected`
- `dialogueEventsSeen`
- `dialogueAnchorsSeen`
- `sceneCommandIdsSeen`
- `sceneDirectiveKindsSeen`
- `scenePhaseSequence`
- `objectivePhaseSequence`
- `resultType`
- `unlockTarget`
- `saveSlotIdentity`
- `resumeTargetScene`
- `resumeTargetStageBinding`

The field keys must exist even when values are unresolved.

## Required Evidence Classes

### 1. Package identity

The harness must record:

- expected APK SHA-256
- installed package path
- installed package SHA-256
- whether the installed package matches the original APK
- device ABI list
- native-bridge state

### 2. JNI call trace

Accepted backends:

- shell/profile backend on a profileable or debuggable build
- rooted backend
- external agent backend
- manually supplied backend artifact from a stronger environment

The harness must always record:

- backend attempted
- whether it was available
- why it failed when unavailable
- where the raw artifact lives when available

### 3. Frame hashes

Accepted backend:

- repeated `adb exec-out screencap -p`

The harness must record:

- capture timestamp
- PNG path
- SHA-256 hash
- focused activity at capture time

### 4. Save snapshots

Accepted backends:

- `run-as`
- rooted backend
- external-storage scan and pull
- manually supplied save artifact

The harness must record:

- backend used
- files discovered
- hashes and sizes of pulled files
- whether the backend was unavailable

### 5. Audio cues

Accepted backends:

- `dumpsys media.audio_flinger`
- `dumpsys audio`
- externally supplied cue timeline

The harness must record:

- timestamps
- package-linked audio sessions
- active track counts
- raw snapshot paths or snippets

### 6. Scene transitions

Accepted backends:

- focused-window/activity polling
- UI dump snapshots
- logcat activity/window lines
- manually supplied scene annotations

The harness must record:

- transition timestamp
- focused component
- optional scene label
- supporting artifact paths

## Tooling

Probe device/package capabilities:

```powershell
python tools/arel_wars2/capture_aw2_oracle_trace.py probe `
  --apk arel_wars2/arel_wars_2.apk `
  --output recovery/arel_wars2/native_tmp/oracle/probe.json
```

Capture a raw oracle session:

```powershell
python tools/arel_wars2/capture_aw2_oracle_trace.py capture `
  --apk arel_wars2/arel_wars_2.apk `
  --capture-id aw2-boot-title-oracle `
  --duration 20 `
  --output-dir recovery/arel_wars2/native_tmp/oracle/boot-title
```

## Current Status

As of `2026-04-03`, the harness exists but the environment is still blocked before capture:

- the original APK is present
- the available x86_64 emulator cannot install it
- the current Android Emulator build on this host cannot boot ARMv7 or ARM64 AVDs

That means the harness is ready, but a usable oracle runtime still requires an external ARM-capable Android environment.
