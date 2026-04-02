# AW1 Verification Protocol

Audit date: 2026-04-02

This document defines how to capture a reference oracle run from the original `arel_wars_1.apk` and store it in a machine-readable structure that later differential tooling can compare against a 64-bit runtime path.

It is narrower than the full equivalence criteria.
Its job is to define:

- what must be captured from the original run
- which capture backends are acceptable
- what field structure the oracle trace must follow
- what to do when a device can run the APK but cannot expose every backend

## Goal

Produce a reference trace from the original APK that includes:

- package identity
- JNI trace backend result
- frame hashes
- save-file evidence
- audio-cue evidence
- scene-transition evidence
- a verification-trace object compatible with later equivalence comparison

## Canonical Inputs

- original APK:
  - [arel_wars_1.apk](/C:/vs/other/arelwars/arel_wars1/arel_wars_1.apk)
- equivalence criteria:
  - [aw1-equivalence-criteria.md](/C:/vs/other/arelwars/docs/aw1-equivalence-criteria.md)
- machine-readable equivalence spec:
  - [aw1_equivalence_spec.json](/C:/vs/other/arelwars/recovery/arel_wars1/aw1_equivalence_spec.json)
- native/main integration note:
  - [aw1-main-branch-disassemble-integration.md](/C:/vs/other/arelwars/docs/aw1-main-branch-disassemble-integration.md)

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

The `verificationTrace` object is the bridge to later comparison.
It intentionally mirrors the stage-trace structure used by later replay and verification tools.

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

Fields may be `null` during raw capture if the device cannot infer them automatically, but the field keys must exist.

## Required Evidence Classes

### 1. Package identity

The harness must record:

- expected original APK SHA-256
- installed package path
- installed package SHA-256
- whether the installed package matches the expected original APK
- device ABI list
- native-bridge state

If the installed package does not match the original APK, the capture is not an oracle capture even if the rest of the tooling works.

### 2. JNI call trace

Accepted backends:

- shell/profile backend on a profileable or debuggable build
- rooted backend
- external agent backend
- manually supplied backend file from a stronger capture environment

The harness must always record:

- which backend was attempted
- whether it was available
- why it failed when unavailable
- where the raw trace artifact lives when available

Current production-style emulator builds may refuse shell profiling on non-profileable apps.
That does not invalidate the harness, but it does mean the current device is not sufficient for a fully passing oracle capture.

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
- rooted device
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
- backend-specific raw snippets or snapshot files

If exact cue naming is not available, the harness should still record session transitions and mark cue identity as unresolved rather than inventing names.

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

## Capture Procedure

1. Connect a device that can execute the original APK.
2. Verify package identity against the original APK hash.
3. Run harness `probe` first.
4. Launch the original package.
5. Run harness `capture` for the target scenario.
6. Preserve the raw artifacts and generated session JSON.
7. If some fields remain unresolved, annotate them later without changing the raw evidence.

## Tooling

Probe device/package capabilities:

```powershell
python tools/arel_wars1/capture_aw1_oracle_trace.py probe `
  --apk arel_wars1/arel_wars_1.apk `
  --output recovery/arel_wars1/native_tmp/oracle/probe.json
```

Capture a raw oracle session:

```powershell
python tools/arel_wars1/capture_aw1_oracle_trace.py capture `
  --apk arel_wars1/arel_wars_1.apk `
  --capture-id boot-title-oracle `
  --duration 20 `
  --output-dir recovery/arel_wars1/native_tmp/oracle/boot-title
```

If the connected device is not currently running the original package, add `--allow-package-mismatch` only for smoke-testing the harness itself.
Do not treat that output as oracle evidence.

## Approval For Phase 2

Phase 2 is approved only when:

1. the harness exists
2. it writes the structured session JSON described above
3. it records package identity and backend capability truthfully
4. it can capture frame hashes, scene transitions, and audio/save evidence on the current device when those backends are available
5. it can capture JNI trace when run on a strong enough backend environment, or records exactly why that backend is unavailable on the current device

The key point is honesty:

- missing backend support must be explicit
- fallback inference must not be disguised as captured truth

## Notes

- Current `disassemble` evidence remains the parser and native-layout authority.
- Current `main` replay/verification exports are useful as a later comparison schema, not as parser truth.
- A session captured from a non-original installed package is only a harness smoke test.
