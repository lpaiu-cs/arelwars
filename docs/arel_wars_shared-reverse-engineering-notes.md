# Arel Wars Shared Reverse-Engineering Notes

This document captures the parts of the recovery work that are likely to stay useful across more than one game build.

## Reusable Tools

- [`inspect_apk_inventory.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars_shared/inspect_apk_inventory.py)
  Fast APK inventory summary. Use it before writing any extractor so path/layout assumptions are explicit.
- [`inspect_gxl_tables.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars_shared/inspect_gxl_tables.py)
  Fast inspector for decoded `GXL` table payloads from `catalog.json`.
- [`read_zt1()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py)
  Stable `ZT1` header + zlib decoder. This already works on both `arel_wars_1.apk` and sampled `arel_wars_2.apk` script/table files.
- [`extract_script_events()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py)
  Heuristic `ZT1` parser for:
  - `caption`: `FF + textLen(u16) + text`
  - `speech`: `prefix + speakerLen(u16) + speaker + speakerTag(u8) + textLen(u16) + text`
- [`parse_script_prefix()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py)
  Converts recovered speech prefixes into structured command records.
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
  - `en`: `55` captions, `3849` speech events
  - `ko`: `57` captions, `3879` speech events
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
- The strongest current reusable prefix rule is:
  - `03 <portraitId> <expression>` => `set-left-portrait`
  - `01 <portraitId> <expression>` => `set-right-portrait`
  - `04 <expression>` => `set-expression`
- Allow multi-word speaker names. Rejecting spaces causes real events such as `Mercenary 1` and `Royal Soldier` to collapse into bogus prefix bytes.

## Arel Wars 1 PZX/MPL Rules That Are Probably Version-Specific

- `arel_wars_1.apk` `PZX`:
  - first zlib stream decodes as chunk-offset table + chunk payloads for `205/205` `variant=8` files
  - later streams split into fixed placement tables or frame/tail metadata
- `arel_wars_1.apk` `MPL`:
  - 6-word header followed by 2 palette banks
  - current best runtime rule: `default bank B, flagged item -> bank A`
- Do not assume those exact rules apply unchanged to later games.

## Known Limits

- `GXL` tables are now structurally recognized, but column-level schema recovery is still open.
  Current high-confidence header model is:
  - `magic = GXL\x01`
  - `rowCount(u16)`
  - `headerExtraSize(u16)`
  - `rowSize(u16)`
  - `headerSize = 10 + headerExtraSize`
  - `payloadSize = rowCount * rowSize`
  This already holds for all currently inspected AW1 and AW2 data tables.

- `179.pzx` in Arel Wars 1 now has a usable `shadeBand * 47 + paletteResidue` preview heuristic, but the original blend equation is still unproven.
- `PTC` is structurally parsed but semantically heuristic.
- `ZT1` parsing is strong on dialogue flow and prefix-command structure, but some non-dialogue/map-state opcode names are still provisional.
- AW2 `PZF` uses a big-endian plain-header offset table before its zlib metadata stream; that header rule is likely reusable across more than one AW2 body-part asset family.
- The AW2 `PZF` plain header is two-stage:
  - first a monotonic big-endian offset run
  - then packed references that split into `groupId(high byte) + localOffset(low 24 bits)`
- AW2 `PZF` zlib metadata is already recoverable enough to branch by variant:
  - `anchor-only`
  - `anchor+marker`
  - `marker-only`
  - `opaque`
- Repeated `11-byte` anchor-box records have now been observed with family-specific strides:
  - effect: `11`
  - head: `18`, `25`
  - weapon / weapon2: `18`, `23`, `30`
  - armor: `53`, `60`
- Dense `67ff000000` sections in AW2 `PZF` are a strong timing/state clue, analogous in spirit to AW1 late-stream tail markers even though the exact record layout is different.
- The first two bytes of AW2 `67ff` payloads are already useful classifier keys.
  Common leading words now seen in samples:
  - `0100`
  - `0200`
  - `0000`
  - `0401`
  These should be treated as candidate control words before attempting a single universal tuple parser.
- Many AW2 `67ff` payloads are now structurally recoverable without naming every field yet.
  The most reusable generic shapes are:
  - `control + int16*`
  - `control + int16* + tail byte`
  - `control + nested 67xx000000 marker`
- `marker-only` AW2 families are the cleanest next target because their payloads often collapse directly into small point-like signed-coordinate tuples.
- Current high-confidence compact tuple cases:
  - `effect/001.pzf`: mostly direct `x,y`
  - `weapon2/003.pzf`: mostly `index,x,y`
- A fast visual sanity check for AW2 body-part assets now exists:
  - [`render_pzf_anchor_probes.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars2/render_pzf_anchor_probes.py)
  - representative outputs under [`pzf_anchor_probes`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/pzf_anchor_probes)
- A complementary point-cloud sanity check now exists for compact marker tuples:
  - [`render_pzf_marker_scatter.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars2/render_pzf_marker_scatter.py)
  - representative outputs under [`pzf_marker_scatter`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/pzf_marker_scatter)
- Sequence-level candidate sheets now exist for the strongest AW2 cases:
  - [`render_pzf_sequence_candidates.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars2/render_pzf_sequence_candidates.py)
  - representative outputs under [`pzf_sequence_candidates`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/pzf_sequence_candidates)
