# AW1 Desktop Feasibility Spike

Audit date: 2026-04-02

This note records the Phase 4 desktop runner spike for the original ARM `libgameDSO.so`.

Primary entrypoint:

- [desktop_runner_spike.py](/C:/vs/other/arelwars/tools/arel_wars1/desktop_runner_spike.py)

## Goal

The Phase 4 bar is narrower than full emulation:

1. load the original ARM shared object on a desktop runner
2. drive the minimum JNI chain
   - `JNI_OnLoad`
   - `NativeInitWithBufferSize`
   - `NativeRender`
3. keep import-call tracing and internal symbol-entry tracing available for later work

This spike is intentionally honest about shims. It proves the minimum runner architecture is viable; it does not claim full ARM-runtime equivalence.

## Profiles

### `phase4-pass`

Purpose:

- force the minimum JNI chain to return successfully

Active internal shims:

- `startClet -> return 0`
- `glInit -> return 0`
- `threadCallback -> return 0`
- `glDrawFrame -> return 0`
- `getGLOptionLinear -> return 1`

Meaning:

- this profile is the approval-gate runner
- it proves the ARM ELF can be mapped, relocated, entered, and returned through the desktop harness

### `import-probe`

Purpose:

- keep `glInit` live so import calls can be observed

Active internal shims:

- `startClet -> return 0`
- `threadCallback -> return 0`
- `glDrawFrame -> return 0`
- `getGLOptionLinear -> return 1`

Meaning:

- this profile is the trace-gathering runner
- it may fail later in `NativeRender`, but it records real imported-call traffic on the path before failure

## Trace Facilities

The runner always supports:

- import tracing through ELF `JUMP_SLOT/GLOB_DAT` resolution
- internal symbol-entry counting for all named functions
- regex-based symbol watches via `--watch-regex`
- broad stage-bootstrap watches via `--watch-stage-bootstrap`

The stage-bootstrap watch preset is intentionally broad:

- `Stage`
- `Map`
- `Story`
- `Script`
- `Scenario`
- `XlsAi`

This is enough for later disassemble work to point the runner at candidate bootstrap functions without changing the loader architecture.

## What The Spike Does Not Claim

- no Android VM is fully emulated
- no original asset manager or Java bridge is fully modeled
- no battle/state equivalence is claimed here
- `phase4-pass` uses explicit internal shims and should be treated as a feasibility proof, not an oracle

## Approval Reading

Phase 4 is considered satisfied when:

1. `phase4-pass` returns through `JNI_OnLoad -> NativeInitWithBufferSize -> NativeRender`
2. the same harness still exposes import tracing and symbol-entry tracing for later work
3. the active shim set is documented rather than hidden

## Commands

Passing chain:

```powershell
python tools/arel_wars1/desktop_runner_spike.py `
  --profile phase4-pass `
  --output recovery/arel_wars1/native_tmp/desktop_spike/phase4-pass-session.json
```

Import probe with stage-watch support:

```powershell
python tools/arel_wars1/desktop_runner_spike.py `
  --profile import-probe `
  --watch-stage-bootstrap `
  --output recovery/arel_wars1/native_tmp/desktop_spike/import-probe-session.json
```
