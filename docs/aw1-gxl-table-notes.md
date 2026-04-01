# AW1 GXL Table Notes

This note tracks the fixed-layout `GXL` table family used under `assets/data_eng/*.zt1` and `assets/data_kor/*.zt1`.

Primary outputs:

- [gxl_table_report.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/gxl_table_report.json)
- [AW1.gxl.summary.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.gxl.summary.json)
- [XlsHero.eng.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/gxl_row_dumps/XlsHero.eng.json)
- [XlsMap.eng.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/gxl_row_dumps/XlsMap.eng.json)
- [XlsLevelDesign.eng.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/gxl_row_dumps/XlsLevelDesign.eng.json)
- [XlsAi.eng.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/gxl_row_dumps/XlsAi.eng.json)
- parsed exports under [parsed_tables](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables)

## Current Header Model

The earlier `rowCount / headerExtra / rowSize` reading was wrong.

Current best model:

- `magic = GXL\x01`
- `field1(u16) = rowSize`
- `field2(u16) = headerExtraSize`
- `field3(u16) = rowCount`
- `headerSize = 10 + headerExtraSize`
- `payloadSize = rowSize * rowCount`

Evidence:

- `XlsHero`
  - `field1=65`, `field2=49`, `field3=6`
  - payload is `390 = 65 * 6`
  - six hero-sized rows is much more plausible than sixty-five 6-byte rows
- `XlsMap`
  - `field1=5`, `field2=5`, `field3=16`
  - payload is `80 = 5 * 16`
  - `16` lines up with the `assets/map/000..015.zt1` count
- `XlsAi`
  - `field1=501`, `field2=78`, `field3=130`
  - payload is `65130 = 501 * 130`

## File-Level Notes

### XlsHero

- English:
  - `rowSize=65`
  - `rowCount=6`
- Korean:
  - `rowSize=64`
  - `rowCount=6`
- Each row begins with a small numeric prelude, then a NUL-terminated localized name.
- Example row starts:
  - row `0`: `00 00 00 04 04 00 Vincent\0 ...`
  - row `1`: `00 01 01 04 0a 00 Helba\0 ...`
  - row `2`: `00 02 02 04 07 00 Juno\0 ...`
- Current candidate hints:
  - byte `2` looks like a stable hero index
  - byte `4` may be a portrait or presentation id because it loosely matches script portrait usage for `Vincent`, `Juno`, and `Caesar`
- The tail of each row contains short monotonic id runs such as:
  - row `0`: `00..0f`
  - row `1`: `10..1f`
  - row `2`: `20..2f`
  These are likely references to related asset ids, skills, or progression slots.
- Parsed English roster currently resolves to:
  - `0 Vincent`
  - `1 Helba`
  - `2 Juno`
  - `3 Manos`
  - `4 Caesar`
  - `5 Rogan`

### XlsMap

- `rowSize=5`
- `rowCount=16`
- First rows:
  - `00 00 e2 03 00`
  - `00 00 e2 02 00`
  - `01 00 d8 02 00`
  - `01 00 d8 03 00`
- Current candidate shape:
  - a small map or world id in the first byte or first `u16`
  - one or two compact coordinate / offset fields in the remaining bytes
- Current parsed `groupId -> pair(valueU16)` clusters are:
  - `0 -> [994, 738]`
  - `1 -> [728, 984]`
  - `2 -> [994, 738]`
  - `3 -> [1250, 482]`
  - `4 -> [1526, 1014]`
  - `5 -> [0, 0]`
  - `6 -> [0, 0]`
  - `7 -> [0, 0]`
- Best next step:
  - compare against `assets/map/000..015.zt1` ordering and the `XlsWorldmap` table

### XlsLevelDesign

- `rowSize=4`
- `rowCount=63`
- Rows are single little-endian `u32` values.
- First rows:
  - `0x00000258`
  - `0x00000834`
  - `0x00000fa0`
  - `0x00002710`
- This is likely not a whole stage row by itself.
- Stronger current guess:
  - `XlsLevelDesign` is a compact scalar table referenced by another table rather than a full human-readable stage definition on its own.
- The first parsed values are:
  - `600, 2100, 4000, 10000, 22000, 36000, 65000, 150000, 8000, 30000, 75000, 200000, 500000, 900000, 2000000, 5000000`
- This looks more like progression thresholds or costs than stage-by-stage map metadata.

### XlsAi

- `rowSize=501`
- `rowCount=130`
- Rows contain a mix of:
  - localized title text
  - fixed numeric fields
  - bonus reward text
  - tactical hint text
- Row `0` structure is already visibly segmented:
  - offset `0x000`: unknown `u16`
  - title text starts at `0x002`: `First Battle`
  - reward text starts at `0x08d`: `Clear the stage in 3 minutes...`
  - hint text starts at `0x117`: `!cffffffThe enemy Knolls...`
- The title block is heavily zero-padded after the first string, which suggests a fixed title slot rather than a free-form string pool.
- Current English slot model used by the parsed export is:
  - `0x000..0x001`: unknown `u16`
  - `0x002..0x01f`: title slot
  - `0x020..0x08c`: numeric block
  - `0x08d..0x116`: reward slot
  - `0x117..0x1d4`: hint slot
  - `0x1d5..0x1f4`: tail slot
- This table is now the best candidate source for:
  - stage names
  - bonus conditions
  - hint text
  - at least part of stage progression metadata
- Parsed English summary currently reports:
  - `130` titled rows
  - `61` rows with a non-empty hint slot
  - first titles include `First Battle`, `Buster Hunt`, `Seize Veril`, `Into the Enemy Camp`, `Arang's Challenge`, `Seize Kaleck`

### XlsWorldmap

- `rowSize=4`
- `rowCount=16`
- Parsed rows are strongly consistent with a small world-graph adjacency table.
- Current high-confidence reading:
  - each row stores up to `4` neighbor slots
  - `0xff` means empty
- Current graph is a simple linear chain:
  - `0 <-> 1 <-> 2 <-> 3 <-> ... <-> 15`

### XlsUnit

- English parsed export now exists under [`XlsUnit.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsUnit.eng.parsed.json).
- Current practical slot model:
  - byte `0`: unknown lead byte
  - bytes `1..76`: name slot plus pre-description numeric fields
  - bytes `77..end`: description slot
- The first parsed unit names are:
  - `Infantry`
  - `Panzer`
  - `Cavalry`
  - `Hunter`
  - `Gliders`
  - `Thief`

### XlsTower

- English parsed export now exists under [`XlsTower.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsTower.eng.parsed.json).
- Current rows are only `2` bytes wide and look like compact pair records:
  - `[0, 0]`
  - `[0, 3]`
  - `[0, 0]`
  - `[1, 2]`
  - `[1, 5]`
  - `[1, 2]`

## Immediate Next Steps

1. Compare `XlsAi` English/Korean rows to isolate localized byte spans from numeric byte spans.
2. Correlate `XlsAi` row order with story/stage order from script files.
3. Cross-reference `XlsMap`, `XlsLevelDesign`, and `XlsWorldmap` to recover stage-to-map binding.
4. Promote the current parsed exports into stronger typed schemas instead of `candidate` / `unknown` fields.
