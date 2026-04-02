# AW1 Main Branch Outputs Worth Reusing On `disassemble`

Audit date: 2026-04-02

This note selects only the `origin/main` outputs that are still useful after the native loader/runtime closure already established on `disassemble`.

Reference points:

- `origin/main` audited at `c302e2c`
- current common base with `disassemble`: `d0383b0`

The rule is simple:

- keep `main` outputs that help choose samples, name render/effect states, or prioritize native consumer tracing
- do not import `main` outputs as byte-level truth when `disassemble` already has a native-confirmed structure

## Reuse Without Reinterpretation

### 1. Regression sample corpus

These `origin/main` artifacts are worth keeping open while tracing native consumers:

- `docs/arel_wars1-recovery.md`
- `recovery/arel_wars1/timeline_candidate_strips/*.json`
- `recovery/arel_wars1/timeline_candidate_strips/*.png`
- `recovery/arel_wars1/frame_meta_group_probes/*.png`

Priority stems:

- `082`: frame pool sanity check. Native side already closes as `raw PZF frameCount = 86`, `raw PZA frameIndex range = 0..85`.
- `084`: mixed anchor/overlay case with one explicit `6700` instant event and a strong loop-window hypothesis.
- `208`: clean base-frame-delta sample. Good for checking whether a marker block is really a `PZF` exposure or an additional effect envelope.
- `209`: single-anchor-with-overlays. Good for comparing repeated overlay cadence against native `PZA delay`.
- `215`: single-anchor-cadence. Best sample for repeated same-frame timing without much pose churn.
- `226`: mixed anchor/overlay donor stem. Good for testing whether long overlay runs correspond to native effect selectors or just heuristic grouping.
- `230`: late-frame contiguous loop candidate. Good sample for native loop/hold behavior.
- `240`: overlay-track-only. Best sample for separating base clip timing from pure secondary effect cadence.

What to take from these files:

- which stems are visually rich enough to use as regression targets
- which event groups are overlay-only versus base-linked
- where `0x00`, `0x07`, `0x78`, `0xC8`, `0xFF` timing-like marker values cluster
- which stems deserve side-by-side comparison between heuristic strips and native `PZA/PZF` decode

What not to take as final truth:

- the claim that the post-frame tail is itself the primary native timeline format
- donor/prototype-derived durations as recovered runtime fields
- heuristic loop windows as authoritative native loop metadata

### 2. Render semantics that already line up with native consumption

These `origin/main` files are useful and mostly orthogonal to the native parser closure:

- `docs/aw1-phase1-10-audit.md`
- `tools/arel_wars1/export_aw1_render_semantics.py`
- `recovery/arel_wars1/parsed_tables/AW1.render_semantics.json`

Safe facts to reuse:

- `MPL` selector rule: `flag == 0 -> bank B`, `flag > 0 -> bank A`
- `179` is a special packed-pixel case, not a general palette rule
- the `179` rule on `main` matches the useful native-consistent view:
  - `0` is transparent
  - normalize with `value - 1`
  - core palette band width is `47`
  - `189..199` behaves as a highlight tail
- `PTC` emitter naming is useful as a consumer-label layer, especially:
  - `support-pulse`
  - `burst-flare`
  - `impact-spark`
  - `utility-trail`
  - `smoke-plume`
  - `guard-ward`
  - `support-ring`
  - `support-shimmer`
  - `support-impact`
  - `mana-drift`
  - `armageddon-burst`

How to use them on `disassemble`:

- annotate native draw/effect consumers with stable names instead of anonymous row numbers
- compare `MPL` bank selection against the already confirmed `flag` split
- keep `179` isolated as a dedicated render path when tracing packed-pixel consumers

### 3. Effect/runtime crosswalks

These are useful as naming and prioritization aids, not as parser specs:

- `recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json`
- `recovery/arel_wars1/parsed_tables/AW1.runtime_blueprint.json`

Useful pieces:

- `AW1.effect_runtime_links.json` summarizes a real `12`-row particle family and already groups shared primaries such as `048`
- the same file gives a workable secondary-PTC histogram and concrete dual-PTC pairings like `046/034`
- `AW1.runtime_blueprint.json` is useful for mapping stage/script/render terminology, but it is an engine-facing synthesis, not native wire format

How to use them on `disassemble`:

- prioritize `CGxEffect*`, `PTC`, and battle-effect consumers by named family instead of raw ids alone
- keep the main-branch names when writing notes, screenshots, and regression labels
- do not let the runtime blueprint override a direct native call graph or a native field layout

## Do Not Import As Truth

These `origin/main` areas are still valuable as prototypes or demos, but they should not be pulled into the native format narrative:

- `recovery/arel_wars1/timeline_candidate_strips/*.json` timing fields such as `playbackDurationMs`, `playbackSource`, `playbackDonorStem`
- `tools/arel_wars1/render_timeline_candidate_strips.py` donor/prototype timing passes
- `tools/arel_wars1/pzx_meta.py` timeline taxonomy as if it were a native enum
- `remake/arel-wars1/*`
- web preview/runtime packaging outputs

Reason:

- `disassemble` already closed the embedded path as `PZX root -> typed PZD/PZF/PZA subresources -> native runtime consumers`
- much of `main`'s older tail/timeline model is a useful visual decomposition of that data, not a replacement for the native structure

## Recommended Working Set

If only a small subset should stay open during native work, use this:

1. `docs/arel_wars1-recovery.md`
2. `recovery/arel_wars1/timeline_candidate_strips/084-timeline-strip.json`
3. `recovery/arel_wars1/timeline_candidate_strips/215-timeline-strip.json`
4. `recovery/arel_wars1/timeline_candidate_strips/226-timeline-strip.json`
5. `recovery/arel_wars1/timeline_candidate_strips/230-timeline-strip.json`
6. `recovery/arel_wars1/timeline_candidate_strips/240-timeline-strip.json`
7. `recovery/arel_wars1/frame_meta_group_probes/208-group00-base-frame-delta.png`
8. `recovery/arel_wars1/frame_meta_group_probes/230-group00-base-frame-delta.png`
9. `recovery/arel_wars1/frame_meta_group_probes/240-group00-overlay-track.png`
10. `recovery/arel_wars1/parsed_tables/AW1.render_semantics.json`
11. `recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json`

This set is enough to answer three practical questions:

- which samples should be used to validate a native timing/effect hypothesis
- which visual behaviors are probably base-linked versus overlay-only
- which render/effect names should be reused when documenting native consumers

## Disassemble-Side Reading Rule

When a `main` artifact says:

- “this event looks plausible”

treat it as a sample-selection hint.

When it says:

- “this field is the timeline”

require a matching native parser or native consumer before accepting it.

For the current embedded APK path, the native baseline remains:

- root offsets are a typed `PZD/PZF/PZA` table
- `PZA` is the authoritative clip/timing carrier where present
- `PZF` owns frame composition and subframe effect payloads
- `PZD` owns the image pool addressed by `subFrameIndex`

Related note:

- see `docs/aw1-main-branch-correction-hints.md` for the hand-off version intended for `main` workers
