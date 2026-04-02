# AW1 Main Branch Correction Hints

This note is for the data-inference workers on `main`.
It summarizes native facts already confirmed on `disassemble` so heuristic work can be re-anchored to the actual loader/runtime graph.

Audit date: 2026-04-02

## What Is Native-Confirmed

### 1. `PZX` root fields are a typed subresource table

The three root offsets are not loose stream hints.
They are the native subresource graph:

- `field4 -> PZD`
- `field8 -> PZF`
- `field12 -> PZA`

Confirmed via the `CGxPZxParserBase::CheckPZxType` path and matching asset-side raw parsing.

Implication:

- always classify a `.pzx` from the root segment layout first
- do not treat later zlib hits as independent peer formats before checking whether they are mirrors of embedded raw `PZF` or `PZA`

### 2. `PZA` is the canonical animation/timeline carrier

For the native embedded path, time-axis playback is driven by `PZA`, not by ad-hoc tail generalization.

Confirmed record shape from `CGxPZAParser::DecodeAnimationData`:

```text
clip:
  frameCount:u8
  repeat frameCount times:
    frameIndex:u16
    delay:u8
    x:s16
    y:s16
    control:u8
```

Runtime consumption:

- `CGxPZAMgr::LoadAni*` uses `frameIndex[]`
- `CGxPZFMgr::LoadFrameEx` loads the real frame payload
- `CGxPZxAni::DoPlay` consumes `delay`

Implication:

- when a stem has embedded `PZA`, treat `delay` as the authoritative playback timing source
- heuristic tail timing should be labeled as inferred playback structure, not native field recovery

### 3. `PZF` owns frame composition, not `PZX tail`

Many stream-1 “frame-record” candidates seen from pure zlib inspection are actually raw embedded `PZF` payloads or partial misreads of that payload.

Native `PZF` frame shape already closes:

```text
frame:
  subFrameCount:u8
  bbox tokens / bbox records
  repeat subFrameCount times:
    subFrameIndex:u16
    x:s16
    y:s16
    extraFlag:u8
    extraPayload:variable
```

Implication:

- if a decoded zlib stream matches embedded `PZF` bytes, classify it as a `PZF` exposure, not a new sibling format
- if `frameIndex` appears larger than a visible base-frame count, compare it to raw `PZF frameCount`, not to first-stream chunk count

Concrete example:

- `082.pzx`
  - raw `PZF frameCount = 86`
  - raw `PZA frameIndex range = 0..85`
  - the old mismatch disappears once measured against `PZF`, not against an earlier heuristic frame count

### 4. `PZD` image pools are already closed

Native-equivalent image mapping is:

- `PZD type 8`: `subFrameIndex == first-stream chunk index`
- `PZD type 7`: `subFrameIndex == row-stream/image index`

Implication:

- overlay/tail chunk-range work should be compared against the correct `PZD` image pool
- do not assume every index-like field is a first-stream chunk reference

### 5. Tail markers are not automatically “native timing opcodes”

Markers such as:

- `67 ff 00 00 00`
- `67 78 00 00 00`
- `67 c8 00 00 00`
- `66 07 00 00 00`
- `66 0c 00 00 00`

are useful clustering anchors, but they are not yet proven to be a single canonical timing grammar in the native embedded path.

Native facts already confirmed:

- `CGxPZFParser::EndDecodeFrame*` stores per-subframe `extraLen + extraPtr`
- `CGxEffectPZDMgr::FindEffectedImage` / `LoadImage*` use that payload in effected-bitmap handling
- standalone `EffectEx/ZeroEffectEx` families use selector-byte tables such as `0x65..0x74`, `0x7f`

Implication:

- keep using these markers for grouping and visualization
- do not promote them to “final native timing fields” without a matching native consumer
- a duration inferred from these markers should stay explicitly marked as heuristic unless proven against a native read path

## Corrections To Apply On Main

### 1. Rename certainty levels more aggressively

Recommended distinction:

- `native-confirmed`
- `asset-structural`
- `runtime-consistent heuristic`
- `donor/prototype inferred`

In particular:

- `playbackDurationMs` values derived from donor/prototype rules should not be described as recovered native timing fields
- `timelineKind` is useful and should stay, but it is a classifier, not a native enum

### 2. Reframe “tail groups” as secondary analysis objects

Use wording like:

- “tail-group candidate”
- “post-frame grouped section”
- “heuristic overlay/linked event”

Avoid wording like:

- “the tail format is”
- “native tail record”

until a matching native parser/consumer is found.

### 3. Re-anchor all timing claims to `PZA` when available

For stems with embedded `PZA`:

- compare heuristic event cadence against native `delay`
- note where heuristic overlay events are additional structure beyond the base `PZA` clip
- separate “base clip timing” from “secondary overlay cadence”

### 4. Re-anchor bank semantics to item flags

Current native-consistent rule:

- `flag == 0 -> MPL bank B`
- `flag > 0 -> MPL bank A`

This is stronger than an overlay-label-only rule.

### 5. Treat `179` as a special packed-pixel case, not a general palette rule

`179` has a native-consistent special mapping:

- transparent `0`
- normalize with `value - 1`
- `47`-color core band
- four main bands
- `189..199` additive highlight tail

Do not generalize that rule onto normal `PZX/MPL` pairs.

## High-Value Regression Stems

These should stay in the main-branch validation set because they align well with native questions:

- `084`: rising-anchor with overlays, explicit loop candidate
- `208`: linked base-frame delta case
- `215`: single-anchor cadence
- `226`: mixed anchor/overlay stem, good donor stem
- `230`: clean rising-anchor late loop
- `240`: overlay-track-only
- `082`: frameCount/frameIndex bound sanity check

## Practical Hand-off Rule

If a main-branch result can be phrased as:

- “this matches a native field or native consumer already identified on `disassemble`”

then it is likely worth promoting.

If it can only be phrased as:

- “this produces a plausible playback sheet”

then it should stay explicitly heuristic, even if visually convincing.
