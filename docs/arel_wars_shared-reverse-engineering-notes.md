# Arel Wars Shared Reverse-Engineering Notes

This document captures the parts of the recovery work that are likely to stay useful across more than one game build.

## Reusable Tools

- [`inspect_apk_inventory.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars_shared/inspect_apk_inventory.py)
  Fast APK inventory summary. Use it before writing any extractor so path/layout assumptions are explicit.
- [`read_zt1()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py)
  Stable `ZT1` header + zlib decoder. This already works on both `arel_wars_1.apk` and sampled `arel_wars_2.apk` script/table files.
- [`extract_script_events()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py)
  Heuristic `ZT1` parser for:
  - `caption`: `FF + textLen(u16) + text`
  - `speech`: `prefix + speakerLen(u16) + speaker + speakerTag(u8) + textLen(u16) + text`
- [`analyze_script_events.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/analyze_script_events.py)
  Builds speaker-tag and opcode-prefix summaries from recovered event dumps.

## Stable ZT1 Rules

- The first `8` bytes are still `packedSize(u32), unpackedSize(u32)`.
- The payload after that is plain zlib.
- Locale-specific scripts should not be hard-coded to `script_eng` / `script_kor`.
  `arel_wars_2.apk` moves those files under:
  - `assets/eng/script/*.zt1`
  - `assets/kor/script/*.zt1`
  - `assets/jpn/script/*.zt1`
- The current event parser already works on sampled `arel_wars_2` files:
  - `assets/eng/script/000.zt1`
  - `assets/kor/script/000.zt1`
  - `assets/jpn/script/000.zt1`

## Arel Wars 1 Script Heuristics Worth Keeping

- Script event coverage is now high enough to be operational:
  - `624` script files parsed
  - `en`: `55` captions, `3637` speech events
  - `ko`: `57` captions, `3862` speech events
- Speaker tags are structurally meaningful even if the exact asset binding is still incomplete.
  Examples from [`script_event_report.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/script_event_report.json):
  - `0`: mostly `Vincent / 빈센트`
  - `1`: mostly `Cecil / 세실`
  - `5`: mostly `Caesar / 케사르`
  - `6`: mostly `Helba / 헬바`
  - `10`: mostly `Rogan / 로간`, with some `Manos / 마노스`
  - `11`: mostly `Juno / 유노`
  - `12`: mostly `Theon / 테온`
- Prefix bytes before speech are also reusable clues.
  High-frequency examples:
  - `00`
  - `03050100`
  - `040700`
  - `040a00`
  - `03070100`
  - `03090100`
  - `030a0100`
- Treat those prefixes as candidate presentation/state opcodes, not junk.

## Arel Wars 1 PZX/MPL Rules That Are Probably Version-Specific

- `arel_wars_1.apk` `PZX`:
  - first zlib stream decodes as chunk-offset table + chunk payloads for `205/205` `variant=8` files
  - later streams split into fixed placement tables or frame/tail metadata
- `arel_wars_1.apk` `MPL`:
  - 6-word header followed by 2 palette banks
  - current best runtime rule: `default bank B, flagged item -> bank A`
- Do not assume those exact rules apply unchanged to later games.

## Known Limits

- `179.pzx` in Arel Wars 1 still carries packed pixel/shading bits beyond the direct palette index path.
- `PTC` remains opaque.
- `ZT1` parsing is strong on dialogue flow but still incomplete for non-dialogue opcodes and map-state commands.
