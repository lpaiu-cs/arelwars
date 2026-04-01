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
