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
- [AW1.map_binding_candidates.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.map_binding_candidates.json)
- [AW1.runtime_field_reuse_scan.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.runtime_field_reuse_scan.json)
- [AW1.battle_catalog.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_catalog.json)
- [AW1.effect_runtime_links.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json)
- [AW1.hero_skill_links.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_skill_links.json)

`AW1.runtime_field_reuse_scan.json` is useful as a filter, but its best exact hits are mostly low-entropy columns such as binary flags or small id ranges.
It did not yet reveal a hard `stage -> map payload` pointer on its own.
Its main value so far is that it elevates `XlsHero_Ai`, `XlsSkill_Ai`, `XlsProjectile`, and `XlsEffect` as the best next typed-schema targets.

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
- A more cautious current reading is that bytes `2` and `3` should still be kept as separate compact fields:
  - `valueLoByte`
  - `valueHiByte`
  The combined little-endian `valueU16` is still useful for clustering, but it is probably not the true semantic field boundary.
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
- Stronger current follow-up from `AW1.map_binding_candidates.json`:
  - only the first `10` rows are non-zero, which makes `5` active group pairs
  - those `5` active group pairs align naturally with map-bin pairs:
    - group `0` -> `000/001`
    - group `1` -> `002/003`
    - group `2` -> `004/005`
    - group `3` -> `006/007`
    - group `4` -> `008/009`
  - groups `5..7` remain zero in `XlsMap`, so `010..015` are not yet explained by this table alone

### assets/map/*.zt1

- These are not `GXL`, but they are now stable enough to treat as a separate fixed-header family.
- Current header reading from [AW1.map_binding_candidates.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.map_binding_candidates.json):
  - `u32 version`
  - `u32 layerCount`
  - `u32 width`
  - `u32 height`
  - `u32 reserved0`
  - `u32 reserved1`
  - `u32 variantOrGroup`
  - `u32 reserved2`
- Representative examples:
  - `000.zt1.bin` -> `version=1, layerCount=3, width=62, height=20, variantOrGroup=3`
  - `006.zt1.bin` -> `version=1, layerCount=2, width=62, height=20, variantOrGroup=3`
  - `008.zt1.bin` -> `version=1, layerCount=4, width=62, height=20, variantOrGroup=8`
- File sizes roughly follow:
  - `2 * layerCount * width * height + meta`
- This is strong evidence that `assets/map/*.zt1` are concrete layered map payloads, not high-level stage rows.

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
- The numeric block is now strong enough to expose reusable runtime-field candidates for script-backed rows:
  - `numericBlock[13]` -> `tierCandidate`
  - `numericBlock[15]` -> `variantCandidate`
  - `numericBlock[16]` -> `regionCandidate`
  - `numericBlock[17]` -> constant `5`
  - `numericBlock[18]` -> `storyFlagCandidate`
- Current histograms over the `111` script-backed rows:
  - `tierCandidate`: `10, 20, 30, 50`
  - `variantCandidate`: `1..6`
  - `regionCandidate`: `5, 6, 7, 9`
  - `storyFlagCandidate`: `0, 1`
- Strongest current interpretation:
  - `regionCandidate` is a chapter or region bucket
  - `variantCandidate` is a local scenario or map-variant selector
  - `storyFlagCandidate` toggles a story-enabled or alternate stage form

### XlsWorldmap

- `rowSize=4`
- `rowCount=16`
- Parsed rows are strongly consistent with a small world-graph adjacency table.
- Current high-confidence reading:
  - each row stores up to `4` neighbor slots
  - `0xff` means empty
- Current graph is a simple linear chain:
  - `0 <-> 1 <-> 2 <-> 3 <-> ... <-> 15`

### XlsHero_Ai

- English parsed export now exists under [`XlsHero_Ai.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsHero_Ai.eng.parsed.json).
- Current practical slot model:
  - byte `0`: `heroIdCandidate`
  - byte `1`: `profileGroupCandidate`
  - bytes `2..15`: compact priority grid
  - bytes `16..23`: timing pattern
  - bytes `24..33`: fallback pattern
- Strongest current reading:
  - rows are grouped by hero id
  - hero ids `0..5` line up with the parsed hero roster in `XlsHero.eng.parsed.json`
  - the repeated `10/20/30/50/100` cadence values look like AI timing or trigger thresholds rather than content ids

### XlsSkill_Ai

- English parsed export now exists under [`XlsSkill_Ai.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsSkill_Ai.eng.parsed.json).
- Current practical slot model:
  - byte `0`: `skillIdCandidate`
  - bytes `1..5`: trigger window A
  - bytes `6..10`: trigger window B
  - bytes `11..12`: tail mode bytes
- Strongest current reading:
  - this is a compact skill-trigger policy table
  - repeated `30/50`, `20/30/50/60`, and tail markers `0xfd/0xfe` look like cooldown or threshold presets
  - ids align more strongly with `XlsItem.itemCodeCandidate` and selected `XlsHeroSkill.aiCodeCandidate` values than with raw row order
  - best current practical label is `item/active-skill AI`

### XlsHeroSkill and XlsItem

- English parsed exports now exist under:
  - [`XlsHeroSkill.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsHeroSkill.eng.parsed.json)
  - [`XlsItem.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsItem.eng.parsed.json)
- `XlsHeroSkill` currently reads as:
  - name slot
  - compact metadata block with `skillCodeCandidate` and `aiCodeCandidate`
  - localized description
- `XlsItem` currently reads as:
  - name slot
  - compact metadata block with `itemCodeCandidate`, `categoryCandidate`, `aiCodeCandidate`, and `costCandidate`
  - localized description
- The linked export [`AW1.battle_catalog.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.battle_catalog.json) now cross-references:
  - `skillIdCandidate -> matchingItemsByItemCode`
  - `skillIdCandidate -> matchingHeroSkillsByAiCode`
- The stronger current hero-skill finding lives in [`AW1.hero_skill_links.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_skill_links.json):
  - `slotOrPowerCandidate` is now a high-confidence direct slot index into `XlsHeroPassiveSkill` for slots `0..23`
  - the same slot index also reaches `24/25` rows in `XlsHeroActiveSkill`
  - current orphan active row is `24`
  - `24/24` passive rows are reachable by hero-skill slot index
  - `21` rows match by exact normalized name
  - slots `6`, `13`, and `23` are alias cases where `Defend Tower` in the master table maps to `Thief/Helba/Juno Tower Defense` in the passive table
  - `XlsHeroBuffSkill.tailLinkCandidate` is also slot-like when non-`255`, currently landing on slots `11`, `14`, `15`, `19`, `20`, `21`, `22`, and `23`
  - slots `29`, `30`, and `31` sit outside the passive table and currently host special `mode 0:2` rows: `Stun`, `Smoke`, and `Armageddon Buff`

### XlsHeroActiveSkill

- English parsed export now exists under [`XlsHeroActiveSkill.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsHeroActiveSkill.eng.parsed.json).
- Current pragmatic reading:
  - `headerBytes`
  - `timingWindowA`
  - `timingWindowB`
  - `tailPairBE`
- The last `8` bytes produce small big-endian pair values such as `[4, 1, 6, 2]`, which are much more plausible as compact ids than the raw little-endian words.
- The correlation export [`AW1.effect_runtime_links.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json) now shows exact runtime-table hits in `5/25` rows:
  - row `0` pair `(4, 1)` exactly matches projectile row `5`
  - row `1` pair `(3, 2)` exactly matches effect row `26`
  - row `2` pair `(3, 0)` exactly matches both projectile row `4` and effect row `24`
- This is still not enough to fully name the tail pair payload, but it is strong evidence that at least part of the block is a direct projectile/effect reference table.
- [`AW1.hero_skill_links.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.hero_skill_links.json) also shows that `XlsHeroActiveSkill` behaves like a parallel slot table:
  - slots `0..23` are all reachable from the hero-skill master table
  - row `24` is present in `XlsHeroActiveSkill` but currently has no hero-skill slot owner
  - slots `19..23` are especially structured, with timing ladders that line up against `Mana Gain`, three `Dispatch` rows, and `Defend Tower`

### XlsHeroBuffSkill

- English parsed export now exists under [`XlsHeroBuffSkill.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsHeroBuffSkill.eng.parsed.json).
- Current pragmatic reading:
  - `familyCandidate`
  - `tierCandidate`
  - `triggerModeCandidate`
  - `magnitudeWindowU8`
  - `skillCodeCandidate`
  - `profileCandidate`
  - `tailLinkCandidate`
- This is still provisional, but rows visibly carry compact skill or profile ids in the low teens and low twenties, which makes it a good next runtime-schema target.
- New slot-link evidence improves that a bit:
  - when `tailLinkCandidate != 255`, the target currently lands on hero-skill slots `11`, `14`, `15`, `19`, `20`, `21`, `22`, and `23`
  - that puts the linked rows close to `Natural Healing`, `HP Up`, `Mana Wall`, `Mana Gain`, the three `Dispatch` rows, and `Defend Tower`

### XlsHeroPassiveSkill

- English parsed export now exists under [`XlsHeroPassiveSkill.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsHeroPassiveSkill.eng.parsed.json).
- Current reading:
  - fixed `20`-byte name slot
  - two little-endian value fields
  - short tail field
- Several names overlap directly with `XlsHeroSkill` entries such as `HP Up`, `Shuriken`, and `Double Attack`.
  This strongly suggests `XlsHeroPassiveSkill` is the stat-definition side of some named hero-skill upgrades.
- The new slot-link report strengthens that reading considerably:
  - passive row `0` -> hero-skill slot `0` -> `HP Up`
  - passive row `4` -> hero-skill slot `4` -> `Snatch`
  - passive row `20/21/22` -> hero-skill slots `20/21/22` -> three `Dispatch` rows
  - passive row `6/13/23` -> slots `6/13/23` -> the three `Defend Tower` master rows

### XlsProjectile

- English parsed export now exists under [`XlsProjectile.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsProjectile.eng.parsed.json).
- Current practical slot model:
  - byte `0`: `familyCandidate`
  - byte `1`: `projectileIdCandidate`
  - byte `2`: `variantCandidate`
  - byte `3`: `speedOrRangeCandidate`
  - byte `4`: `motionCandidate`
  - bytes `5..12`: tail block with sentinel-heavy metadata
- Strongest current reading:
  - this table is small, fixed, and highly likely to be the projectile runtime definition table
  - `0xff`-heavy tail fields suggest optional effect/sound links or unused slots

### XlsEffect

- English parsed export now exists under [`XlsEffect.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsEffect.eng.parsed.json).
- Current practical slot model:
  - byte `0`: `familyCandidate`
  - byte `1`: `effectIdCandidate`
  - byte `2`: `variantCandidate`
  - byte `3`: `frameOrDurationCandidate`
  - byte `4`: `loopFlagCandidate`
  - byte `5`: `blendFlagCandidate`
  - byte `6`: `extraModeCandidate`
  - byte `7`: sentinel, usually `0xff`
  - byte `8`: tail byte

### XlsBaseAttack, XlsParticle, XlsBalance, XlsCorrespondence

- Parsed exports now also exist for:
  - [`XlsBaseAttack.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsBaseAttack.eng.parsed.json)
  - [`XlsParticle.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsParticle.eng.parsed.json)
  - [`XlsBalance.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsBalance.eng.parsed.json)
  - [`XlsCorrespondence.eng.parsed.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/XlsCorrespondence.eng.parsed.json)
- `XlsParticle` is especially likely to matter for runtime reconstruction because it is a tiny id bridge table and lines up naturally with `PTC`/effect work.
- [`AW1.effect_runtime_links.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.effect_runtime_links.json) now makes that linkage much stronger:
  - all `12/12` primary `XlsParticle` ids map directly to existing `ptc/NNN.ptc` files
  - all `10/10` nonzero secondary ids also map directly to `ptc/NNN.ptc`
  - the repeated primary id `48` across rows `0, 1, 7, 8, 9` looks like a shared emitter template with alternate secondary embellishment layers
- `XlsCorrespondence` currently looks like a `5 x 7` slot-mask table rather than free-form data.
- Strongest current reading:
  - this is a compact effect playback definition table rather than a content string table
  - early rows look like family-indexed effect variants with one-byte loop/blend flags

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
3. Use the new `tier/variant/region/storyFlag` candidates to search the remaining battle/runtime payloads for the first hard stage-to-map pointer.
4. Promote `XlsHero_Ai`, `XlsSkill_Ai`, `XlsProjectile`, and `XlsEffect` from byte-block candidates to named gameplay schemas.
