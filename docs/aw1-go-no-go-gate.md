# AW1 Go / No-Go Gate

## Goal

Phase 9 is the decision gate between:

- continuing in-app ARM emulation work
- stopping emulation and switching to oracle-driven 1:1 porting

The gate is intentionally strict. A partial renderer or partially playable port is not enough.

## Gate Tool

- evaluator: [evaluate_aw1_go_no_go_gate.py](/C:/vs/other/arelwars/tools/arel_wars1/evaluate_aw1_go_no_go_gate.py)
- latest verdict: [phase9-gate.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/go_no_go_gate/phase9-gate.json)

Inputs used by the evaluator:

- [phase4-pass-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/desktop_spike/phase4-pass-session.json)
- [phase5-trace-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/desktop_spike/phase5-trace-session.json)
- [phase8-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/differential_suite/phase8-session.json)
- `origin/main:recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json`
- `origin/main:recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json`

Reference trace:

- `000-run-1`

Expected binding from `origin/main`:

- `familyId = 000`
- `aiIndex = 0`
- `preferredMapIndex = 1`

## Gate Criteria

Desktop side must prove:

- `JNI_OnLoad`
- `surface init`
- `first render`
- `3+ seconds stable execution`

In-app side must prove:

- boot path works
- actual runtime `familyId/aiIndex/preferredMapIndex` matches the reference binding
- at least one scripted battle trace matches the oracle trace
- orientation and home/resume preserve battle continuity
- retreat flow still behaves correctly

## Current Verdict

Latest verdict: `no-go`

Failed checks:

- `stable3Seconds`
- `familyAiPreferredMapMatch`
- `scriptedBattleTraceMatch`
- `orientationLifecycle`

Passing checks:

- desktop `JNI_OnLoad`
- desktop `surface init`
- desktop `first render`
- in-app boot path
- in-app retreat flow

## Why It Failed

### 1. No 3-second stable desktop run evidence

The desktop spike proves:

- `JNI_OnLoad`
- `NativeInitWithBufferSize`
- `NativeRender`
- import tracing
- first-render marker reach

It does not yet prove a steady 3-second render loop under the desktop runner.

### 2. Runtime binding fields are not exposed from the in-app ARM path

The current in-app session still cannot report actual:

- `familyId`
- `aiIndex`
- `preferredMapIndex`

for the running ARM-backed path.

Without those fields, the equivalence gate cannot pass.

### 3. Scripted battle trace does not match

The differential suite shows:

- oracle expects `battle` at 30 seconds
- current in-app run reaches `result` before that oracle point

That alone is enough to fail the scripted-trace requirement.

### 4. Lifecycle continuity still breaks

The differential suite also shows:

- orientation drops battle back to `title`
- home/resume returns to `result` instead of preserving active `battle`

## Required Decision

Because the verdict is `no-go`, the approved next path is:

- stop in-app emulation as the primary track
- switch to oracle-driven 1:1 porting

That means:

- use the ARM path as the oracle
- keep the desktop/in-app emulation tools only for instrumentation and evidence gathering
- move the implementation focus back to exact runtime-state reconstruction against oracle traces

## Command

```powershell
python tools/arel_wars1/evaluate_aw1_go_no_go_gate.py
```
