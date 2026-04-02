# AW1 Disassemble Branch Review

This note summarizes what the `disassemble` branch currently proves, what `main` should keep using, and what must remain heuristic until original-equivalence certification.

Review date: 2026-04-02

Branch reviewed:

- `disassemble`
- tip: `bab79bf` `Refine AW1 main regression alignment checks`

Primary review inputs:

- `/Users/lpaiu/Downloads/aw1-main-branch-correction-hints.md`
- `docs/arel_wars1-disassembly-progress.md` on `disassemble`
- `docs/aw1-main-branch-disassemble-integration.md` on `disassemble`
- `docs/arel_wars1-disassembly.md` on `disassemble`

## What The Disassemble Branch Has Closed

The strongest native-confirmed progress is in the render and animation loader stack.

- `PZX` root offsets are typed subresources:
  - `field4 -> PZD`
  - `field8 -> PZF`
  - `field12 -> PZA`
- `PZA` clip structure is closed enough to treat as native base timing truth when present.
  - clip frame entries carry `frameIndex`, `delay`, `x`, `y`, `control`
- `PZF` frame structure is closed enough to treat as native frame-composition truth.
  - each frame record is `subFrameIndex + x/y + extra payload`
- `PZD` raw image-pool layouts are closed for the current APK set.
  - type `8`: chunk index aligns with the old first-stream sheet
  - type `7`: row-stream index aligns with the old image index
- `PZxFrameBB` and related bounding-box semantics are substantially resolved.
- `CGxPZxAni` playback state is substantially resolved.
  - native base timing uses `delay + globalDelayBias`
  - current APK appears to leave `globalDelayBias` dormant
- `EffectEx / ZeroEffectEx` selector tables and draw-op routing are substantially resolved.
  - important point: much of this path appears dormant in the current APK

## What This Changes On Main

The most important correction is that `main` must keep `native base clip timing` separate from `runtime overlay grouping`.

- `PZA delay` is the canonical native timing source for a base clip when embedded `PZA` exists.
- `timelineKind`, grouped tail overlays, donor-filled timings, and `playbackDurationMs` are not native timing proof.
- `PZF` owns frame composition.
- `PZD` owns the underlying image pool.
- `PZA -> PZF -> PZD` is the stack that original-equivalence work should measure against.

## Strong Findings Worth Reusing As-Is

- `MPL` bank switching rule:
  - `flag == 0 -> bank B`
  - `flag > 0 -> bank A`
- `179` should stay a special packed-pixel case.
- `PTC` emitter naming from `main` is still useful as a runtime-facing label layer.
- The eight-stem regression corpus remains the right short-loop certification set:
  - `082`
  - `084`
  - `208`
  - `209`
  - `215`
  - `226`
  - `230`
  - `240`

## What Main Must Not Overclaim

These should stay out of any “native-confirmed” wording:

- `timeline_candidate_strips/*.json` timing as if it were direct native timing
- `playbackDurationMs` as if it were recovered from `PZA delay`
- `timelineKind` as if it were a native enum
- grouped tail markers `66/67` as if their consumer semantics were fully closed
- donor/prototype timing fills as if they were original-engine truth

The disassemble regression comparator explicitly showed that current main timing sheets do not directly overlap native `PZA delay` values on the regression set. They remain useful for runtime playback, but they are not the same thing as native clip timing.

## Concrete Takeaways For Future Certification

### 1. Use Two Timing Layers

- `native clip timing`:
  - from `PZA`
  - used for equivalence certification
- `runtime overlay cadence`:
  - from grouped tail heuristics
  - used for current remake playback until a native consumer is matched

### 2. Keep Render Truth Layered

- `PZD/PZF/PZA`: native-confirmed or asset-structural truth
- `MPL flag -> bank`: strong/native-aligned rule
- `179`: asset-specific special handling
- `PTC` emitter semantics: runtime-consistent reconstruction unless matched to native code

### 3. Treat Dormant Native Paths Carefully

Do not expand current remake logic just because a native path exists in disassembly.

Known examples:

- `globalDelayBias`
- reference-point mode in the current APK
- parts of `EffectEx / ZeroEffectEx`

If the current APK does not exercise them, they belong in reference notes, not in forced runtime behavior.

## Tooling On The Disassemble Branch Worth Mirroring Or Reusing

- `tools/arel_wars1/compare_main_regression_set.py`
- `tools/arel_wars1/audit_apk_runtime.py`
- `tools/arel_wars1/verify_current_apk_closure.py`
- `tools/arel_wars1/disassemble_libgameDSO.py`

These are most useful for certification and audit work, not for day-to-day runtime iteration.

## Recommended Main-Branch Policy

Until original-equivalence certification is complete, `main` should use these certainty labels consistently:

- `native-confirmed`
- `asset-structural`
- `runtime-consistent heuristic`
- `donor/prototype inferred`

That policy already matches [aw1-native-branch-alignment.md](/Users/lpaiu/vs/others/arelwars/docs/aw1-native-branch-alignment.md). This document extends it by recording which disassemble-branch findings are strong enough to drive the next certification stage.
