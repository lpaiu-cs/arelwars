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
  - chunk records with `width(u16)`, `height(u16)`, `02 CD CD CD`, `declaredPayloadLen(u32)`, `reserved(u32)`
  - row-oriented RLE bodies where each row expands to exactly `width` bytes via alternating `skip(u16)` and `literal(0x80nn + nn bytes)` commands
  - `FE FF` row separators and an optional trailing `FF FF` sentinel after the last row
- `.mpl`
  Partially decoded by pattern. For 63 paired stems, 61 files match a strong regular form:
  - `actualWordCount = 2 * (maxPzxIndex + 1) + 6`
  - this strongly suggests a 6-word header followed by two palette banks sized to the indexed colors used by the paired `.pzx`
  - heuristic `RGB565` renders from those two banks already produce sprite-like chunk previews
  - known outliers so far: `145.mpl`, `179.mpl`
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
2. Firm up `.mpl` into a real palette parser, including the two known outliers and any bank-selection metadata.
3. Turn extracted script data into structured event commands instead of raw string previews.
4. Stand up a Phaser-side asset preview that can swap from synthetic placeholders to decoded `.pzx` and heuristic `.mpl` colors.

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

- For 61 of 63 paired stems, `mplActualWords = 2 * (maxPzxIndex + 1) + 6`.
- That regularity strongly suggests:
  - `PZX` first-stream output is palette-indexed image data
  - `MPL` carries two palette banks after a 6-word header
- Heuristic RGB565 probes already produce sprite-like colored chunk sheets for stems such as `198`, `208`, and `240`.
