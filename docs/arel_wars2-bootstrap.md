# Arel Wars 2 Bootstrap Notes

This is the shortest path for starting `arel_wars_2.apk` with the least wasted motion.

## First Facts

Use [`apk_inventory.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/apk_inventory.json) before adapting any `arel_wars1` tool.

High-level layout differences from Arel Wars 1:

- `arel_wars_1.apk`
  - `700` `.zt1`
  - `256` `.pzx`
  - `65` `.mpl`
  - `50` `.ptc`
  - main asset roots: `img`, `script_eng`, `script_kor`, `data_eng`, `data_kor`
- `arel_wars_2.apk`
  - `530` `.zt1`
  - `393` `.pzx`
  - `107` `.mpl`
  - `63` `.pzd`
  - `16` `.pzf`
  - `51` `.ptc`
  - main asset roots: `img`, `pc`, `eng`, `kor`, `jpn`, `script`, `table`, `sound`, `plasma`

## What Reuses Cleanly

- `ZT1` header + zlib decoding reuses directly.
- The current `ZT1` event parser also works on sampled AW2 localized script files:
  - `assets/eng/script/000.zt1`
  - `assets/kor/script/000.zt1`
  - `assets/jpn/script/000.zt1`
- AW2 script text is therefore a good first target. It is the lowest-risk way to get immediate narrative structure back.
- `tools/arel_wars2/extract_assets.py` now exists and already rebuilds:
  - `recovery/arel_wars2/catalog.json`
  - `recovery/arel_wars2/decoded/zt1/.../*.strings.txt`
  - `recovery/arel_wars2/decoded/zt1/.../*.events.json`
- `tools/arel_wars1/analyze_script_events.py` also works on the AW2 catalog and now emits [`script_event_report.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/script_event_report.json).

## What Does Not Reuse Cleanly

- AW1 path assumptions do not hold:
  - localized scripts are under `assets/{eng,kor,jpn}/script/`
  - there is also a separate non-localized `assets/script/`
  - table data lives under `assets/table/*.zt1`
- AW1 `MPL` assumptions do not hold:
  - sampled AW2 `assets/pc/armor/0/000.mpl` is only `2` bytes, so it is not the same “6-word header + 2 full palette banks” structure used by AW1 `assets/img/*.mpl`
- AW1 `PZX` first-stream decoder does not apply directly:
  - sampled AW2 `assets/img/145.pzx` still starts with `PZX\x01`
  - but its first zlib stream does not decode into an offset table; it starts with dense byte data and AW1 `read_pzx_first_stream()` rejects it
  - AW2 `145.pzx` also exposes many more zlib streams (`22` in the sample), so metadata layering is likely deeper

## New Formats Introduced In AW2

- `PZD`
  - sampled file: `assets/pc/armor/0/000.pzd`
  - magic: `PZD\x02`
  - contains multiple embedded zlib streams
  - those decoded payloads already parse cleanly as AW1-style row-RLE images
  - `tools/arel_wars2/render_pzd_previews.py` now produces pseudo-color preview sheets under `recovery/arel_wars2/pzd_previews/`
- `PZF`
  - present in `16` files
  - now partially inspected
  - magic: `PZF\x01`
  - uses a plain-header big-endian offset table before a large zlib metadata stream
  - after the initial monotonic offset run, later `u32` words split cleanly into:
    - `groupId = high byte`
    - `localOffset = low 24 bits`
  - decoded zlib metadata is no longer opaque:
    - several families expose repeated `11-byte` anchor-box records
    - some families also expose dense `67ff000000`-delimited timing/state sections
    - those marker payloads are themselves patterned; common leading control words include `0100` and `0200`
    - current numeric recovery shows many marker payloads reduce to:
      - `control + int16 fields`
      - `control + int16 fields + tail byte`
      - `control + nested secondary marker`
    - compact coordinate recovery now distinguishes two especially useful subcases:
      - `effect/001.pzf`: mostly direct `x,y` tuples
      - `weapon2/003.pzf`: mostly `index,x,y` tuples
  - current variant split is:
    - `anchor-only`: armor `000/001`, head `000/001/002`
    - `anchor+marker`: effect `000/002`, weapon `000/001/002`, weapon2 `000/001/002`
    - `marker-only`: effect `001`, weapon2 `003`
    - `opaque`: armor `002`
  - current common anchor strides include:
    - armor: `53`, `60`
    - head: `18`, `25`
    - weapon: `18`, `30`
    - weapon2: `18`, `23`, `30`
    - effect: `11`
  - this strongly suggests `PZF` is the animation/state sidecar for `PZD` body-part sprites, with family-specific record layouts
  - immediate next parse target:
    - branch `67ff` payload grammar by leading control word and section length, not just by file family
  - highest-confidence current subcase:
    - `marker-only` families such as `effect/001.pzf` and `weapon2/003.pzf` already look like small point-like control tuples
  - current best sequence-candidate cases:
    - `weapon2/003.pzf`: strong `index -> point cluster` grouping
    - `weapon2/000.pzf`: `anchor+marker` case with matched `PZD` body-part overlays
    - `effect/000.pzf`: large control-word overlay family with reusable point clouds
- `plasma/`
  - large Samsung/Android UI asset subtree; likely not core gameplay data

## Current AW2 State

These steps are now complete:

1. APK inventory
   - [`apk_inventory.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/apk_inventory.json)
2. Script extraction and event recovery
   - [`catalog.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/catalog.json)
   - [`script_event_report.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/script_event_report.json)
3. Binary format scan
   - [`binary_asset_report.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/binary_asset_report.json)
4. First visual proof on `PZD`
   - preview sheets under `recovery/arel_wars2/pzd_previews/`
5. First `PZF -> PZD` anchor probe overlays
   - probe renders under [`pzf_anchor_probes`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/pzf_anchor_probes)
6. First compact-marker scatter probes
   - point-cloud renders under [`pzf_marker_scatter`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/pzf_marker_scatter)
7. First body-part sequence candidate sheets
   - composite sheets and JSON summaries under [`pzf_sequence_candidates`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/pzf_sequence_candidates)

## Recommended Order For AW2 From Here

1. Run [`inspect_apk_inventory.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars_shared/inspect_apk_inventory.py) on the APK.
2. Clone `ZT1` extraction first, not sprite extraction.
   - Adapt paths for `assets/{eng,kor,jpn}/script`, `assets/script`, and `assets/table`.
   - Reuse [`read_zt1()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py) and [`extract_script_events()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py).
3. Use `PZD` as the main image source for AW2 `pc/*`.
   - `PZD` already gives you row-RLE image frames.
4. Use `PZF` as the state/timeline sidecar.
   - Parse it in this order:
     - initial monotonic big-endian offset run
     - packed `group:offset24` references that follow it
     - zlib metadata stream
   - Then branch by variant:
     - `anchor-only`
     - `anchor+marker`
     - `marker-only`
     - `opaque`
5. Only after `PZD/PZF` are in hand should you revisit AW2 `img/*.pzx`.
   - AW2 `img/*.pzx` still decode partly, but they are no longer the cleanest entry point for character content.

## Concrete Starting Commands

```bash
python3 tools/arel_wars_shared/inspect_apk_inventory.py \
  --apk arel_wars2/arel_wars_2.apk \
  --output recovery/arel_wars2/apk_inventory.json
```

```bash
python3 tools/arel_wars2/extract_assets.py \
  --apk arel_wars2/arel_wars_2.apk \
  --output recovery/arel_wars2
```

```bash
python3 tools/arel_wars2/inspect_binary_assets.py \
  --assets-root recovery/arel_wars2/apk_unzip/assets \
  --output recovery/arel_wars2/binary_asset_report.json
```

```bash
python3 tools/arel_wars2/render_pzd_previews.py \
  --assets-root recovery/arel_wars2/apk_unzip/assets \
  --output recovery/arel_wars2/pzd_previews
```

```bash
python3 tools/arel_wars2/render_pzf_anchor_probes.py \
  --assets-root recovery/arel_wars2/apk_unzip/assets \
  --output recovery/arel_wars2/pzf_anchor_probes
```

```bash
python3 tools/arel_wars2/render_pzf_marker_scatter.py \
  --assets-root recovery/arel_wars2/apk_unzip/assets \
  --output recovery/arel_wars2/pzf_marker_scatter
```

```bash
python3 tools/arel_wars2/render_pzf_sequence_candidates.py \
  --assets-root recovery/arel_wars2/apk_unzip/assets \
  --output recovery/arel_wars2/pzf_sequence_candidates
```

For quick script sanity checks, reuse AW1 helpers in a one-off Python session:

```python
from tools.arel_wars1.formats import read_zt1, extract_script_events
```

## Practical Warning

If you treat AW2 as “AW1 plus more files,” you will lose time. The script layer is reusable, `PZD` row streams are reusable, but `PZF` and AW2-side `PZX/MPL` semantics are their own problem.
