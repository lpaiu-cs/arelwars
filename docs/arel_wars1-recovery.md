# Arel Wars 1 Recovery

`arel_wars1/arel_wars_1.apk` is the only surviving artifact for the first game. The original Android/C++ project is gone, so this repo now treats the APK as the recovery source of truth.

## Current Direction

- Runtime target: `Phaser + TypeScript + Vite`
- Mobile packaging target: `Capacitor` after the game shell and recovered assets are stable
- Why: the original APK bundles only 32-bit native ARM code and cannot be rebuilt for `arm64-v8a` or iOS from source

## Recovery Layout

- `recovery/arel_wars1/apk_unzip/`
  Raw APK extraction.
- `recovery/arel_wars1/jadx/`
  Decompiled Java and Android resources from `jadx`.
- `recovery/arel_wars1/decoded/zt1/`
  Decoded `.zt1` payloads plus string previews where text extraction succeeds.
- `recovery/arel_wars1/catalog.json`
  Full machine-readable catalog of extracted formats and `.zt1` entries.
- `remake/arel-wars1/`
  Phaser/Vite remake workspace.

## Known Formats

- `.zt1`
  Confirmed. First 8 bytes are header metadata followed by a zlib payload.
- `.pzx`
  Partially decoded. The first zlib stream in 205 files is now readable as:
  - a 32-bit chunk offset table whose byte span is `field16 >> 6`
  - chunk records with `width(u16)`, `height(u16)`, a `?? CD CD CD` mode tag, `declaredPayloadLen(u32)`, `reserved(u32)`
  - row-oriented RLE bodies where each row expands to exactly `width` bytes via `skip(u16)`, `literal(0x80nn + nn bytes)`, and `repeat(0xC0nn + one value byte)` commands
  - `FE FF` row separators and an optional trailing `FF FF` sentinel after the last row
  - `variant=7` assets such as `180.pzx` appear to reuse the same row grammar directly in each zlib stream, without the outer chunk table/header layer
  - later zlib streams now split into at least two metadata families:
    - a simple fixed `10-byte` placement table used by `022`-`027`, `078`, and `179`
    - frame-record streams used by stems such as `198`, `208`, and `240`, where each record starts with `itemCount`, `frameType`, `x`, `y`, `width`, `height`, then a list of chunk placements
  - some frame-record assets interleave `5-byte` control chunks (`66 0c 00 00 00`, `67 ff 00 00 00`, and relatives) both inside and after records, so later streams still carry a second layer of animation metadata beyond pure chunk placement
  - the frame-record tails can now be split into marker-delimited secondary blocks using `67 ff 00 00 00`, `67 78 00 00 00`, `66 05 00 00 00`, `66 0a 00 00 00`, and `66 0c 00 00 00`
  - many of those secondary blocks decode exactly as `7-byte` flagged tuples: `chunkIndex(u16), x(i16), y(i16), flag(u8)`
- `.mpl`
  Partially decoded by pattern. For all 65 paired stems, the current best model is:
  - the file layout is a 6-word header followed by two palette banks
  - in 61 stems, `actualWordCount = 2 * (maxPzxIndex + 1) + 6` exactly
  - `180.pzx` reaches the same exact fit through raw row-stream decoding rather than the chunk-table path
  - `145.pzx` and `229.pzx` only use a subset of their available palette entries, so their banks are larger than the observed max index requires
  - `179/180` and `145/146` also show explicit shared-`MPL` reuse across stems
  - this strongly suggests a 6-word header followed by two palette banks sized to the indexed colors used by the paired `.pzx`
  - heuristic `RGB565` renders from those two banks already produce sprite-like chunk previews
  - there are no remaining paired-stem blockers at the file-format level; the open work is now palette-bank selection and whole-sprite assembly
- `.ptc`
  Still opaque. Likely particle or effect definitions.

## Commands

From the repo root:

```bash
python3 tools/arel_wars1/extract_assets.py \
  --apk arel_wars1/arel_wars_1.apk \
  --output recovery/arel_wars1 \
  --web-root remake/arel-wars1/public/recovery

python3 tools/arel_wars1/inspect_binary_assets.py \
  --assets-root recovery/arel_wars1/apk_unzip/assets \
  --output recovery/arel_wars1/binary_asset_report.json

python3 tools/arel_wars1/render_pzx_previews.py \
  --assets-root recovery/arel_wars1/apk_unzip/assets \
  --output recovery/arel_wars1/pzx_previews \
  --stems 145 198 208

python3 tools/arel_wars1/render_mpl_palette_probes.py \
  --assets-root recovery/arel_wars1/apk_unzip/assets \
  --output recovery/arel_wars1/mpl_palette_probes \
  --stems 198 208 240

python3 tools/arel_wars1/render_composite_probes.py \
  --assets-root recovery/arel_wars1/apk_unzip/assets \
  --output recovery/arel_wars1/analysis_preview2 \
  --stems 179

python3 tools/arel_wars1/render_frame_meta_group_probes.py \
  --assets-root recovery/arel_wars1/apk_unzip/assets \
  --output recovery/arel_wars1/frame_meta_group_probes \
  --stems 208 230 240 225 084

python3 tools/arel_wars1/render_frame_sequence_candidates.py \
  --assets-root recovery/arel_wars1/apk_unzip/assets \
  --output recovery/arel_wars1/frame_sequence_candidates \
  --stems 208 230 240 225 084

python3 tools/arel_wars1/render_timeline_candidate_strips.py \
  --assets-root recovery/arel_wars1/apk_unzip/assets \
  --output recovery/arel_wars1/timeline_candidate_strips \
  --stems 209 215 226 228 230 084 240

python3 tools/arel_wars1/export_runtime_preview.py \
  --report recovery/arel_wars1/binary_asset_report.json \
  --sequence-root recovery/arel_wars1/frame_sequence_candidates \
  --timeline-root recovery/arel_wars1/timeline_candidate_strips \
  --web-root remake/arel-wars1/public/recovery
```

From `remake/arel-wars1/`:

```bash
npm install
npm run dev
npm run android:debug
npm run ios:sync
```

## Current Build Status

- Android
  Native Capacitor project generated and debug build succeeded.
  Output: `remake/arel-wars1/android/app/build/outputs/apk/debug/app-debug.apk`
- iOS
  Native Capacitor/Xcode project generated successfully.
  Local build is blocked until full Xcode is installed and selected.
  Current failure: `xcode-select: error: tool 'xcodebuild' requires Xcode`
- Web Runtime
  `sync:recovery` now exports `preview_manifest.json`, sequence summaries, and timeline strips into `remake/arel-wars1/public/recovery/analysis/`.
  The Vite runtime reads those files to render:
  - a Phaser-side rotating timeline carousel for representative stems, now backed by per-event candidate frame playback
  - a DOM-side featured timeline gallery fed from the same manifest

## Immediate Next Targets

1. Use the now-complete first-stream `.pzx` decode to recover chunk placement and the role of later zlib streams.
2. Firm up `.mpl` into a real palette parser, including bank-selection metadata and oversized-bank handling.
3. Decode the control-heavy tail sections that begin with markers such as `67 ff 00 00 00`; they likely hold timeline or state-transition metadata layered on top of the frame records.
4. Turn extracted script data into structured event commands instead of raw string previews.
5. Stand up a Phaser-side asset preview that can swap from synthetic placeholders to decoded `.pzx` and heuristic `.mpl` colors.

## PZX Findings

- `headerA` is the decoded row width in bytes.
- `headerB` is the real row count for the chunk.
- The body length is compressed command data, not raw pixels.
- Each row expands to exactly `headerA` bytes, so a chunk yields `headerA * headerB` decoded index bytes.
- 205/205 `variant=8` first-stream containers now decode successfully.
- Example decoded chunk sizes:
  - `145.pzx` chunk `0`: `5 x 14`
  - `198.pzx` chunk `0`: `21 x 18`
  - `208.pzx` chunk `0`: `24 x 23`
- Some chunk bodies begin with `FD FF` before row `0`.
- Most chunks end with `FE FF FF FF`.
- `variant=7` files can skip the chunk-table wrapper entirely and expose standalone row-RLE images as individual zlib streams.
- `179.pzx` has a second zlib stream that parses cleanly as `30` fixed `10-byte` placement records, one per decoded chunk.
- The same simple placement pattern also appears in a small portrait/single-frame group: `022`, `023`, `024`, `025`, `026`, `027`, and `078`.
- Those placement records are enough to build a first whole-sprite composite probe for `179`, although the chunk pixel bytes still appear to carry packed shading/effect bits above the final color index.
- A broader `frame-record` family is now recognized in later zlib streams for `51` stems.
  - `198.pzx` stream `1` parses as `9` frame records and consumes `400 / 486` bytes before a trailing metadata tail.
  - `208.pzx` stream `1` parses as `17` frame records and consumes `1618 / 1966` bytes. Its records carry a recurring in-record control block `66 0c 00 00 00`.
  - `240.pzx` stream `1` parses as `21` frame records and consumes `1812 / 2734` bytes.
- The current working frame-record model is:

```text
record header:
  itemCount:u16
  frameType:u8  (observed value: 1)
  x:i16
  y:i16
  width:u16
  height:u16

then itemCount chunk placements:
  chunkIndex:u16
  x:i16
  y:i16
  flag:u8

optional 5-byte control chunks may appear:
  - between item groups inside a record
  - between consecutive records
  - at the start of a trailing secondary section
```

- `208`, `240`, and `084` all leave a non-empty tail after the frame-record prefix. Those tails repeatedly contain `67 ff 00 00 00`, which is now the strongest candidate marker for a second animation/timeline metadata layer.
- The tail parser now splits those post-frame sections into `773` marker-delimited blocks across all recognized frame-record assets.
  - Marker usage is dominated by `67 ff 00 00 00` (`671` blocks), followed by `66 07 00 00 00` (`34`), `66 05 00 00 00` (`27`), `67 78 00 00 00` (`25`), `66 0a 00 00 00` (`15`), `67 c8 00 00 00` (`6`), and `66 0c 00 00 00` (`5`).
  - `329` blocks already decode exactly as `flagged-tuples`, and another `14` fit `3-byte header + flagged-tuples`.
  - At least `21` stems expose exact-fit tail blocks, including `082`, `083`, `084`, `208`, `225`, `226`, and `240`.
- Grouping those sections by `opaque` separators produces `430` tail groups.
  - `33` groups already have an exact tuple overlap with at least one base frame record.
  - `89` groups are fully tail-only and use chunk indices that never appear in the base frame stream.
  - Current coarse group classes are:
    - `base-frame-delta`: `21`
    - `overlay-track`: `89`
    - `chunk-linked-reuse`: `32`
    - `mixed-or-unknown`: `20`
    - `opaque-only`: `268`
- Concrete examples:
  - `084.pzx` has `67 ff` blocks that decode directly into `3`-tuple and `10`-tuple flagged placement groups.
  - `208.pzx` has `66 0c` blocks that decode into `8`-tuple flagged placement groups, even though the surrounding tail remains only partially decoded.
  - `240.pzx` has many short `67 ff` singleton blocks such as `2e 00 02 00 e6 ff 01`, which fits `chunk=46, x=2, y=-26, flag=1`.
- Connection-rule examples:
  - `208.pzx` tail group `0` overlaps base frame `16` on `6 / 8` exact placements, so at least some `66 0c` tail groups are frame-linked deltas rather than independent tracks.
  - `230.pzx` tail sections collapse into `8` groups; every group links back to base frames, with exact overlaps up to `10 / 10` against late frames `13`-`15`.
  - `240.pzx` tail sections collapse into `5` groups, all tail-only. Their chunk ranges advance as `46-47`, `46-47`, `47-48`, `48-50`, `49-51`, which strongly suggests a separate overlay/effect track layered on top of the base sprite animation.
  - `225.pzx` mostly lands in `chunk-linked-reuse`: its groups share many chunk indices with base frames but rarely the exact same `(chunk, x, y, flag)` tuples, suggesting a reusable secondary pose/effect layer.
  - `084.pzx` has mixed behavior: some groups are tail-only (`52`-`61`), others are `chunk-linked-reuse`, and several central groups become `base-frame-delta` with `7`-`8` exact overlaps against frames `9`-`12`.
- Sequence-candidate sheets now exist in `recovery/arel_wars1/frame_sequence_candidates/`.
  - The gallery now covers all `21` stems whose frame-record tails currently produce non-empty sequence candidates.
  - `208` is currently `single-anchor-delta`: one `base-frame-delta` group anchored at frame `16`.
  - `209` is also `single-anchor-delta`, but with `8` overlay-only groups reusing the same tail chunk range `18-34`, which looks like a fixed base pose plus repeated circular effect layers.
  - `230` is currently `has-contiguous-rise` with a best contiguous anchor run `[13, 14, 15]`, which fits the late-frame loop hypothesis.
  - `084` is also `has-contiguous-rise`, with a central run `[9, 10, 11, 12]`.
  - `215` is `single-anchor-repeat`: nine linked groups all anchor to frame `10`, plus one tiny overlay-only chunk `26`, which looks more like repeated effect deltas than a true frame-to-frame loop.
  - `226` and `228` sit between the clean cases: both keep a small linked anchor set while also emitting separate tail-only overlays, which is a good sign that linked deltas and effect tracks are intentionally mixed in the same tail format.
  - `240` is `overlay-only`, with no base-frame anchor and a clean advancing overlay chunk sequence.
- Timeline strips now exist in `recovery/arel_wars1/timeline_candidate_strips/`.
  - The strip set also covers all `21` active stems, so each candidate tail event can now be read in group-index order instead of as isolated probes.
  - `209-timeline-strip.png` shows a concrete `single-anchor-with-overlays` pattern: one base-linked pose at frame `14`, followed by a `7`-panel repeated circular overlay run.
  - `215-timeline-strip.png` shows `single-anchor-cadence`: the same anchor frame `10` reused across a long sequence of tiny linked deltas before a final overlay event.
  - `226-timeline-strip.png` shows `mixed-anchor-overlay`: a long prefix of overlay-only events tied to frame `0`, then two linked anchor updates (`0`, then `5`).
  - `240-timeline-strip.png` confirms `overlay-track-only`: every event is unanchored and the chunk ranges expand from `46-47` to `49-51` without touching any base frame.
- Strip JSON exports now also carry recovered timing and loop hints.
  - Every marker block is normalized into a raw timing value; the current histogram across active frame-record assets is `0`, `50`, `70`, `80`, `100`, `120`, `150`, `180`, `200`, and `255`.
  - The runtime no longer treats `255` (`67ff`) as a direct duration when a non-`ff` marker is present in the same event. It is now treated as a sentinel/default hold, and the event duration is derived from non-`ff` tail markers first, then anchor-record control markers, then local forward/back-fill.
  - `209` now resolves to a short `50`-unit linked intro, a `100`-unit overlay run, and a `70`-unit tail close.
  - `215` now reads as a real cadence pattern instead of a flat `255` hold: `120 -> 70 -> 70 -> 80 -> 70 -> 120 -> 70`.
  - `226` now exposes a more plausible overlay timeline: `120`, then `200`, then a long `200`-unit run, ending on a `100`-unit close.
  - `230` now derives a consistent `120`-unit late-frame loop by borrowing non-`ff` control markers from anchor frames `13` and `14`.
  - `240` and most of `084` still have no trustworthy local non-`ff` duration source. They now fall back to a separate `global-record-default=120`, which is derived from the dominant non-`ff` frame-record control value across the APK, instead of being silently flattened to `255`.
  - `084` still keeps one explicit `0`-unit instant event (`6700`) as a genuine zero-duration marker; that value is no longer propagated into neighboring events.
  - A second timing pass now borrows cadence only for stems that are still fully unresolved after the local pass, and only when a close donor stem exists inside the same `timelineKind`.
  - The current donor-backed overlay cadence set is `219`, `238`, `239`, and `240`, all of which now borrow from `226`:
    - `219`: `120 -> 200 -> 100`
    - `238`: `120 -> 100`
    - `239`: `120 -> 200 -> 100`
    - `240`: `120 -> 200 -> 200 -> 200 -> 100`
  - The same donor pass now also resolves two previously flat single-event linked stems:
    - `203`: `70` via donor `236`
    - `214`: `100` via donor `193`
  - A narrower local pass now also learns `overlay` timing prototypes from resolved `(tupleCount, markerCount)` shapes when the recovered durations stay within a tight spread.
    - `228`'s lone `before-linked` overlay (`tupleCount=3`, `markerCount=4`) now resolves locally to `70` instead of staying on the global `120`.
    - `084` now resolves both `after-linked` `tupleCount=3`, `markerCount=4` overlays to `70` through the same prototype rule.
  - `084` also has one nearby `opaque-only` `6778` timing cue group, which is now attached to its large `before-linked` overlay. That event still lands on `120`, but it is now sourced from a local cue rather than the APK-wide default.
  - `228`'s linked base pose is still left on `global-record-default=120`; there is not yet a trustworthy local or donor-linked prototype for that exact shape.
  - `230` and `084` now export explicit loop windows based on their strongest contiguous anchor runs:
    - `230`: event loop `1-3`
    - `084`: event loop `5-8`
- Each timeline strip export now also writes per-event combined frames under `recovery/arel_wars1/timeline_candidate_strips/frames/<stem>/`.
  - Those event frames are now copied into the web runtime and used by the Phaser scene as lightweight candidate playback.
- The runtime export now packages those results into `public/recovery/analysis/preview_manifest.json`.
  - Current featured stems are `084`, `230`, `209`, `215`, `226`, `082`, and `203`.
  - The manifest currently summarizes `21` active stems and `7` timeline classes for the web preview.
  - Each featured stem now exports `eventFrames[]` with raw `timingMarkers`, derived `playbackDurationMs`, `playbackSource`, and an inferred `loopSummary`, so the Phaser preview no longer uses a single fixed playback delay.
  - Donor-backed timings now also carry `playbackDonorStem` and `playbackDonorScore` so the runtime manifest preserves which stems still rely on borrowed cadence.
- Visual probes now exist for representative stems in `recovery/arel_wars1/frame_meta_group_probes/`.
  - `208-group00-base-frame-delta.png` shows the `66 0c` tail group sitting on top of anchor frame `16`.
  - `230-group00-base-frame-delta.png` confirms that one late-frame tail group is almost a direct frame delta, not a separate track.
  - `240-group00-overlay-track.png` shows the tail as a standalone star/cross overlay with no matching base-frame chunk positions.
  - `084-group06-base-frame-delta.png` and `225-group06-base-frame-delta.png` give mixed-character examples where the tail is smaller than the full base frame but still composes coherently.
- This means the tail is not one monolithic blob. It is a stream of smaller metadata blocks, some of which are already structured enough to drive placement/state transitions once the block-to-frame relationship is recovered.
- The row grammar currently held by the tools is:

```text
[optional chunk prefix marker: FD FF]
repeat:
  [optional skip:u16]
  literal opcode: 0x8xxx with 14-bit length + literal bytes
  or
  repeat opcode: 0xCxxx with 14-bit length + one byte repeated that many times
until row width is satisfied for the current row
then consume FE FF as the row separator
```

- This decoder is enough to render chunk-level pseudo-color previews even though true palettes and whole-sprite assembly are still unresolved.

## MPL Findings

- For 61 paired stems, `mplActualWords = 2 * (maxPzxIndex + 1) + 6` exactly.
- `180.pzx` adds one more exact match once its raw row streams are considered instead of only chunk-table assets.
- `145.pzx` and `229.pzx` fit the same two-bank layout, but their observed indices only use a subset of the available palette entries.
- Shared-file reuse is explicit in two places:
  - `145.mpl == 146.mpl`
  - `179.mpl == 180.mpl`
- `179` remains special inside that shared-palette pair:
  - `180` fits the palette directly with raw row-stream indices `0..46`
  - `179` can now be spatially assembled from its placement stream, but its chunk bytes range up to `199`, so some upper bits likely encode shading or effect state instead of direct palette slots
- With exact matches, oversized-bank fits, and shared-file reuse combined, all 65 paired stems now fit the current two-bank palette hypothesis.
- Heuristic RGB565 probes already produce sprite-like colored sheets for stems such as `198`, `208`, `229`, and `240`, plus `180` on the raw row-stream path.
