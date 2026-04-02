# AW1 Native Import Shim

Audit date: 2026-04-02

This note records the Phase 5 import-shim state for the desktop ARM runner.

Primary implementation:

- [desktop_runner_spike.py](/C:/vs/other/arelwars/tools/arel_wars1/desktop_runner_spike.py)

Primary evidence:

- [phase5-trace-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/desktop_spike/phase5-trace-session.json)
- [import-probe-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/desktop_spike/import-probe-session.json)

## Goal

Phase 5 closes the host import layer for the desktop runner:

1. original ARM imports are resolved to host handlers
2. import families are explicit
   - memory
   - file
   - socket
   - time
   - GLES1
3. the GL side is allowed to be trace-only rather than onscreen
4. `NativeRender` must still reach a first-render marker

## Implemented Families

### Memory

Host handlers exist for:

- `malloc`
- `free`
- `memset`
- `memcpy`
- `memmove`

### File

Host handlers exist for:

- `fopen`
- `fclose`
- `fread`
- `fwrite`
- `fseek`
- `ftell`
- `access`
- `stat`
- `rename`
- `unlink`

Current behavior:

- `fopen` returns a host-backed pseudo `FILE*`
- if the guest path resolves to a real host path, bytes are read from that file
- otherwise an empty in-memory stream is created

### Socket

Host handlers exist for:

- `socket`
- `connect`
- `send`
- `recv`
- `select`
- `shutdown`
- `close`
- `fcntl`
- `inet_addr`

Current behavior:

- these are offline-safe stubs
- they are resolved and callable from the ARM binary even if the current minimal render path does not hit them

### Time

Host handlers exist for:

- `time`
- `gettimeofday`
- `localtime`
- `ceil`

### GLES1

Host handlers exist for all imported GLES1 calls in the current ELF, including:

- `glDisable`
- `glHint`
- `glEnableClientState`
- `glTexEnvf`
- `glEnable`
- `glActiveTexture`
- `glGenTextures`
- `glBindTexture`
- `glTexParameterx`
- `glTexImage2D`
- `glClearColorx`
- plus the remaining imported GLES1 entrypoints listed in the session JSON

Current GL mode:

- `trace-only`

Meaning:

- the host GLES1 handlers do not present a real framebuffer
- they record imported GL traffic and keep the ARM side running far enough to mark the first render path

## Phase 5 Result

The runner now has a dedicated `phase5-trace` profile.

Active internal shims in this profile:

- `startClet -> return 0`
- `threadCallback -> return 0`
- `getGLOptionLinear -> return 1`
- `glDrawFrame -> mark first-render and return 0`

Important distinction:

- import handling is real for the imported families above
- the `glDrawFrame` internal shim is only a render-marker shim so the first render can be acknowledged without requiring a full Android/driver-backed frame path

## Evidence

From [phase5-trace-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/desktop_spike/phase5-trace-session.json):

- `passedSequence = true`
- `JNI_OnLoad = true`
- `NativeInitWithBufferSize = true`
- `NativeRender = true`
- `firstRenderReached = true`
- `renderMarkerReached = true`
- `renderMarkerSymbol = glDrawFrame`

Observed GLES1 imports on the first-render path include:

- `glDisable`
- `glHint`
- `glEnableClientState`
- `glTexEnvf`
- `glEnable`
- `glActiveTexture`
- `glGenTextures`
- `glBindTexture`
- `glTexParameterx`
- `glTexImage2D`
- `glClearColorx`

This is enough for Phase 5 because the host import layer is no longer the blocker. Remaining work shifts upward to JNI/Android bridge behavior and later in-app runner integration.

## Commands

Phase 5 trace profile:

```powershell
python tools/arel_wars1/desktop_runner_spike.py `
  --profile phase5-trace `
  --output recovery/arel_wars1/native_tmp/desktop_spike/phase5-trace-session.json
```

Supplementary import probe:

```powershell
python tools/arel_wars1/desktop_runner_spike.py `
  --profile import-probe `
  --watch-stage-bootstrap `
  --output recovery/arel_wars1/native_tmp/desktop_spike/import-probe-session.json
```
